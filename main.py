import datetime
import json
import random
import re
import threading
import time

import requests
from eth_account import Account
from eth_account.messages import encode_defunct
from fake_headers import Headers
from loguru import logger
from siwe import SiweMessage
from web3 import Web3

with open('wallets.txt', 'r') as file:
    private_keys = []
    for wallet in file.readlines():
        mnemonic_pattern = r'(\b\w+\b(?:\s+\b\w+\b){11,23})'
        if re.findall(mnemonic_pattern, wallet):
            private_keys.append(Account.from_mnemonic(wallet).key)
        else:
            private_keys.append(wallet.strip())

with open("proxies.txt", "r") as f:
    proxies_list = []
    for proxy in f.readlines():
        if proxy.strip() == "":
            continue
        proxies_list.append(proxy)
    print(f"Total proxies: {len(proxies_list)}")


def checkin(private_key: str, proxy: str):
    proxy = f'http://{proxy}'
    proxies = {
        "http": proxy,
        "https": proxy
    }

    headers = Headers(
        browser="chrome",
        os="win",
        headers=False
    ).generate()

    account = Account.from_key(private_key)
    session = requests.Session()
    session.proxies = proxies
    session.headers = headers

    response = session.post('https://reiki.web3go.xyz/api/account/web3/web3_nonce', json={
        "address": Web3.to_checksum_address(account.address),
    })

    nonce = response.json()['nonce']

    siwe_message: SiweMessage = SiweMessage(message={
        "domain": "reiki.web3go.xyz",
        "address": Web3.to_checksum_address(account.address),
        "chain_id": 56,
        "nonce": nonce,
        "uri": "https://reiki.web3go.xyz",
        "version": "1",
        "issued_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    })

    message = siwe_message.prepare_message()

    signature = account.sign_message(
        encode_defunct(text=message)
    ).signature.hex()

    response = session.post('https://reiki.web3go.xyz/api/account/web3/web3_challenge', json={
        "address": Web3.to_checksum_address(account.address),
        "nonce": nonce,
        "challenge": json.dumps({'msg': message}),
        "signature": signature
    })

    token = response.json()['extra']['token']
    date = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        response = session.put(f"https://reiki.web3go.xyz/api/checkin?day={date}", headers={
            "Authorization": "Bearer " + token,
            **headers
        }, proxies=proxies)

        if response.status_code == 200:
            logger.success(f"{account.address} - {response.status_code}")
            time.sleep((60 * 60 * 24) + random.randint(0, 3600 * 3))
        else:
            logger.error(f"{account.address} - {response.status_code}")
    except Exception as e:
        logger.error(f"{account.address} - {e}")


for idx, private_key in enumerate(private_keys):
    proxy = proxies_list[idx % len(proxies_list)].strip()
    threading.Thread(target=checkin, args=(private_key, proxy)).start()
