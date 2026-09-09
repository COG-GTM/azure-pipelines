package com.contoso.financial.portfolio;

public final class App {
    private App() {
    }

    public static void main(String[] args) {
        Portfolio portfolio = new Portfolio();
        portfolio.add(new Position("CONT", 12, 125.50));
        portfolio.add(new Position("FIN", 8, 92.25));
        System.out.printf("portfolio-api: total value %.2f%n", portfolio.totalValue());
    }
}
