pub fn simulate_paths(start: f64, drift: f64, steps: usize, seed: u64) -> Vec<f64> {
    let mut state = seed;
    let mut value = start;
    let mut paths = Vec::with_capacity(steps);

    for _ in 0..steps {
        state = state
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1);
        let noise = ((state >> 32) as u32) as f64 / u32::MAX as f64 - 0.5;
        value *= 1.0 + drift + noise * 0.01;
        paths.push(value);
    }

    paths
}

pub fn mean(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }

    values.iter().sum::<f64>() / values.len() as f64
}

#[cfg(test)]
mod tests {
    use super::{mean, simulate_paths};

    #[test]
    fn simulation_is_deterministic_for_a_seed() {
        assert_eq!(
            simulate_paths(100.0, 0.01, 8, 42),
            simulate_paths(100.0, 0.01, 8, 42)
        );
    }

    #[test]
    fn simulation_returns_requested_length() {
        assert_eq!(simulate_paths(100.0, 0.01, 5, 42).len(), 5);
    }

    #[test]
    fn mean_handles_constant_series() {
        assert_eq!(mean(&[2.0, 2.0, 2.0]), 2.0);
    }

    #[test]
    fn mean_of_empty_series_is_zero() {
        assert_eq!(mean(&[]), 0.0);
    }
}
