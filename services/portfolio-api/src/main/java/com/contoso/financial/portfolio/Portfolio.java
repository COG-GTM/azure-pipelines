package com.contoso.financial.portfolio;

import java.util.ArrayList;
import java.util.List;

public final class Portfolio {
    private final List<Position> positions = new ArrayList<>();

    public void add(Position position) {
        for (int index = 0; index < positions.size(); index++) {
            Position existing = positions.get(index);
            if (existing.symbol().equals(position.symbol())) {
                double combinedQuantity = existing.quantity() + position.quantity();
                double combinedValue = existing.quantity() * existing.price()
                        + position.quantity() * position.price();
                double combinedPrice = combinedQuantity == 0
                        ? 0
                        : combinedValue / combinedQuantity;
                positions.set(index, new Position(position.symbol(), combinedQuantity, combinedPrice));
                return;
            }
        }
        positions.add(position);
    }

    public double totalValue() {
        return positions.stream()
                .mapToDouble(position -> position.quantity() * position.price())
                .sum();
    }

    public double weight(String symbol) {
        double total = totalValue();
        if (total == 0) {
            return 0;
        }
        return positions.stream()
                .filter(position -> position.symbol().equals(symbol))
                .mapToDouble(position -> position.quantity() * position.price())
                .sum() / total;
    }
}
