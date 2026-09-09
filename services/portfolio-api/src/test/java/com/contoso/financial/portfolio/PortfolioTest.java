package com.contoso.financial.portfolio;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class PortfolioTest {
    @Test
    void emptyPortfolioHasZeroValue() {
        assertEquals(0, new Portfolio().totalValue(), 0.0001);
    }

    @Test
    void totalValueIncludesEveryPosition() {
        Portfolio portfolio = new Portfolio();
        portfolio.add(new Position("CONT", 2, 10));
        portfolio.add(new Position("FIN", 3, 4));

        assertEquals(32, portfolio.totalValue(), 0.0001);
    }

    @Test
    void weightsSumToOne() {
        Portfolio portfolio = new Portfolio();
        portfolio.add(new Position("CONT", 2, 10));
        portfolio.add(new Position("FIN", 3, 10));

        assertEquals(1, portfolio.weight("CONT") + portfolio.weight("FIN"), 0.0001);
    }

    @Test
    void unknownSymbolHasZeroWeight() {
        Portfolio portfolio = new Portfolio();
        portfolio.add(new Position("CONT", 2, 10));

        assertEquals(0, portfolio.weight("UNKNOWN"), 0.0001);
    }

    @Test
    void addingSameSymbolAccumulatesQuantityAndValue() {
        Portfolio portfolio = new Portfolio();
        portfolio.add(new Position("CONT", 2, 10));
        portfolio.add(new Position("CONT", 3, 20));

        assertEquals(80, portfolio.totalValue(), 0.0001);
        assertEquals(1, portfolio.weight("CONT"), 0.0001);
    }
}
