#include "OrderBookEntry.h"
#include <iostream>

OrderBookEntry::OrderBookEntry() {
    this->price = this->amount = 0;
    this->updateId = 0;
}

OrderBookEntry::OrderBookEntry(double price, double amount, int64_t updateId) {
    this->price = price;
    this->amount = amount;
    this->updateId = updateId;
}

OrderBookEntry::OrderBookEntry(const OrderBookEntry &other) {
    this->price = other.price;
    this->amount = other.amount;
    this->updateId = other.updateId;
}

OrderBookEntry &OrderBookEntry::operator=(const OrderBookEntry &other) {
    this->price = other.price;
    this->amount = other.amount;
    this->updateId = other.updateId;
    return *this;
}

bool operator<(OrderBookEntry const &a, OrderBookEntry const &b) {
    return a.price < b.price;
}

void truncateOverlapEntries(std::set<OrderBookEntry> &bidBook, std::set<OrderBookEntry> &askBook) {
    std::set<OrderBookEntry>::reverse_iterator bidIterator = bidBook.rbegin();
    std::set<OrderBookEntry>::iterator askIterator = askBook.begin();
    while (bidIterator != bidBook.rend() && askIterator != askBook.end()) {
        const OrderBookEntry& topBid = *bidIterator;
        const OrderBookEntry& topAsk = *askIterator;
        if (topBid.price >= topAsk.price) {
            if (topBid.updateId > topAsk.updateId) {
                askBook.erase(askIterator++);
            } else {
                std::set<OrderBookEntry>::iterator eraseIterator = (std::next(bidIterator)).base();
                bidIterator++;
                bidBook.erase(eraseIterator);
            }
        } else {
            break;
        }
    }
}

double OrderBookEntry::getPrice() {
    return this->price;
}

double OrderBookEntry::getAmount() {
    return this->amount;
}

int64_t OrderBookEntry::getUpdateId() {
    return this->updateId;
}
