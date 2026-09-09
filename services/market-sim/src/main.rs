use market_sim::{mean, simulate_paths};

fn main() {
    let paths = simulate_paths(100.0, 0.001, 12, 42);
    let final_value = paths.last().copied().unwrap_or(100.0);
    println!(
        "market-sim: {} steps, final {:.2}, mean {:.2}",
        paths.len(),
        final_value,
        mean(&paths)
    );
}
