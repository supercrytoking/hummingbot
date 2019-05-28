#ifndef _ORDER_BOOK_ENTRY_H
#define _ORDER_BOOK_ENTRY_H

#include <stdint.h>
#include <set>
#include <iterator>

class OrderBookEntry {
    double price;
    double amount;
    int64_t updateId;

    public:
        OrderBookEntry();
        OrderBookEntry(double price, double amount, int64_t updateId);
        OrderBookEntry(const OrderBookEntry &other);
        OrderBookEntry &operator=(const OrderBookEntry &other);
        friend bool operator<(OrderBookEntry const &a, OrderBookEntry const &b);
        friend void truncateOverlapEntries(std::set<OrderBookEntry> &bidBook, std::set<OrderBookEntry> &askBook);

        double getPrice();
        double getAmount();
        int64_t getUpdateId();
};

#endif
