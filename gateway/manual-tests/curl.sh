# you need to install to programs: curl and envsubst

# You must the following values in your command line
# GATEWAY_CERT and GATEWAY_KEY are file paths that should match
# the cert files in the same place as CERT_PATH from /conf/gateway-config.yml

# Here are some examples
# export ETH_PRIVATE_KEY='0000000000000000000000000000000000000000000000000000000000000001'
# export GATEWAY_CERT='/home/hummingbot/gateway/certs/client_cert.pem'
# export GATEWAY_KEY='/home/hummingbot/gateway/certs/client_key.pem'

# -k is --insecure, this disables certificate verfication and should only be
# used for local development and testing


# TEST SERVERS

# test that the gateway-api server is running
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:5000/ | jq

# test that the gateway-api ethereum server is running
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:5000/eth | jq

curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:5000/eth/uniswap | jq

# test configuration retrieval and update
curl -s -X GET -k --key $GATEWAY_KEY --cert $GATEWAY_CERT https://localhost:5000/config | jq

curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/config_update.json)" https://localhost:5000/config/update | jq


# TEST Ethereum
# get Ethereum balances for your private key
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_balances.json)" https://localhost:5000/eth/balances | jq

# get Ethereum allowances for your uniswap on private key
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_allowances.json)" https://localhost:5000/eth/allowances | jq

# approve uniswap allowance on your private key
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_approve.json)" https://localhost:5000/eth/approve | jq

# approve uniswap allowance on your private key
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_approve_with_fees.json)" https://localhost:5000/eth/approve | jq

# remove uniswap allowance on your private key
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_remove_allowance.json)" https://localhost:5000/eth/approve | jq

# get the next nonce you should use for your private key
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_nonce.json)" https://localhost:5000/eth/nonce | jq

# call approve with a nonce, if the nonce is incorrect, this should fail
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_approve_with_nonce.json)" https://localhost:5000/eth/approve | jq

# poll the status of an ethereum transaction
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_poll.json)" https://localhost:5000/eth/poll | jq

# cancel a transaction. Note: modify to send the nonce of the transaction to be canceled
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_cancel.json)" https://localhost:5000/eth/cancel | jq


# TEST Uniswap

# get the price of a trade
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_uniswap_price.json)" https://localhost:5000/eth/uniswap/price | jq

# perform a trade
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_uniswap_trade.json)" https://localhost:5000/eth/uniswap/trade | jq

# perform a trade with custom fees
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/eth_uniswap_trade_with_fees.json)" https://localhost:5000/eth/uniswap/trade | jq



# TEST Avalanche

# get the next nonce you should use for your private key
curl -s -X POST -k --key $GATEWAY_KEY --cert $GATEWAY_CERT -H "Content-Type: application/json" -d "$(envsubst < ./requests/avalanche_nonce.json)" https://localhost:5000/avalanche/nonce | jq
