Runnable Rust scaffold for the market-sim migration demo.
It provides a deterministic simulation library and command-line summary.
Run `cargo run --release` from this directory.
Needs Rust/Cargo 1.78 or newer: `Cargo.lock` is lockfile version 4, which older Cargo (such as Ubuntu 24.04's apt `cargo` 1.75) refuses to parse. Install a current toolchain with [rustup](https://rustup.rs).
Rust also needs a C linker: on a minimal Ubuntu, `cargo run` fails with "linker `cc` not found" until you run `sudo apt-get install build-essential`.
