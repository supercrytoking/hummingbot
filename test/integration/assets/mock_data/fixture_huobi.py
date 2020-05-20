class FixtureHuobi:
    GET_ACCOUNTS = {"status": "ok", "data": [{"id": 11899168, "type": "spot", "subtype": "", "state": "working"}]}

    GET_BALANCES = {"status": "ok", "data": {"id": 11899168, "type": "spot", "state": "working",
                                             "list": [{"currency": "lun", "type": "trade", "balance": "0"},
                                                      {"currency": "husd", "type": "trade", "balance": "0.0146"},
                                                      {"currency": "eth", "type": "trade", "balance": "0.226546"}
                                                      ]}}

    ORDER_PLACE = {"status": "ok", "data": "69092298194"}

    ORDER_GET_LIMIT_BUY_FILLED = {"status": "ok",
                                  "data": {"id": 69092298194, "symbol": "ethusdt", "account-id": 11899168,
                                           "client-order-id": "buy-ethusdt-1581561936007620",
                                           "amount": "0.060000000000000000", "price": "286.850000000000000000",
                                           "created-at": 1581561936082, "type": "buy-limit",
                                           "field-amount": "0.060000000000000000",
                                           "field-cash-amount": "5.464200000000000000",
                                           "field-fees": "0.000040000000000000", "finished-at": 1581561936222,
                                           "source": "spot-api", "state": "filled", "canceled-at": 0}}

    ORDER_GET_LIMIT_SELL_FILLED = {"status": "ok",
                                   "data": {"id": 69094165877, "symbol": "ethusdt", "account-id": 11899168,
                                            "client-order-id": "sell-ethusdt-1581562860006536",
                                            "amount": "0.060000000000000000",
                                            "price": "259.110000000000000000", "created-at": 1581562860124,
                                            "type": "sell-limit", "field-amount": "0.060000000000000000",
                                            "field-cash-amount": "5.455400000000000000",
                                            "field-fees": "0.010910800000000000", "finished-at": 1581562860240,
                                            "source": "spot-api", "state": "filled", "canceled-at": 0}}

    ORDER_GET_MARKET_BUY = {"status": "ok", "data": {"id": 69094699396, "symbol": "ethusdt", "account-id": 11899168,
                                                     "client-order-id": "buy-ethusdt-1581563124007518",
                                                     "amount": "5.460000000000000000", "price": "0.0",
                                                     "created-at": 1581563124085, "type": "buy-market",
                                                     "field-amount": "0.060015396458814472",
                                                     "field-cash-amount": "5.459999999999999816",
                                                     "field-fees": "0.000040030792917629", "finished-at": 1581563124185,
                                                     "source": "spot-api", "state": "filled", "canceled-at": 0}}

    ORDER_GET_MARKET_SELL = {"status": "ok", "data": {"id": 69095353390, "symbol": "ethusdt", "account-id": 11899168,
                                                      "client-order-id": "sell-ethusdt-1581563456004786",
                                                      "amount": "0.060000000000000000", "price": "0.0",
                                                      "created-at": 1581563456081, "type": "sell-market",
                                                      "field-amount": "0.060000000000000000",
                                                      "field-cash-amount": "5.459200000000000000",
                                                      "field-fees": "0.010918400000000000",
                                                      "finished-at": 1581563456183, "source": "spot-api",
                                                      "state": "filled", "canceled-at": 0}}

    ORDER_GET_LIMIT_BUY_UNFILLED = {"status": "ok",
                                    "data": {"id": 69095996284, "symbol": "ethusdt", "account-id": 11899168,
                                             "client-order-id": "buy-ethusdt-1581563740035369",
                                             "amount": "0.060000000000000000", "price": "244.640000000000000000",
                                             "created-at": 1581563742607, "type": "buy-limit", "field-amount": "0.0",
                                             "field-cash-amount": "0.0", "field-fees": "0.0", "finished-at": 0,
                                             "source": "spot-api", "state": "submitted", "canceled-at": 0}}

    ORDER_GET_LIMIT_SELL_UNFILLED = {"status": "ok",
                                     "data": {"id": 69095996284, "symbol": "ethusdt", "account-id": 11899168,
                                              "client-order-id": "buy-ethusdt-1581563740035369",
                                              "amount": "0.060000000000000000", "price": "244.640000000000000000",
                                              "created-at": 1581563742607, "type": "sell-limit", "field-amount": "0.0",
                                              "field-cash-amount": "0.0", "field-fees": "0.0", "finished-at": 0,
                                              "source": "spot-api", "state": "submitted", "canceled-at": 0}}

    ORDER_GET_CANCELED = {"status": "ok", "data": {"id": 69095996284, "symbol": "ethusdt", "account-id": 11899168,
                                                   "client-order-id": "buy-ethusdt-1581563740035369",
                                                   "amount": "0.060000000000000000", "price": "244.640000000000000000",
                                                   "created-at": 1581563742607, "type": "buy-limit",
                                                   "field-amount": "0.0", "field-cash-amount": "0.0",
                                                   "field-fees": "0.0", "finished-at": 1581563762817,
                                                   "source": "spot-api", "state": "canceled",
                                                   "canceled-at": 1581563762755}}

    ORDERS_BATCH_CANCELLED = {"status": "ok", "data": {"success": ["69098120228", "69098120253"], "failed": []}}
