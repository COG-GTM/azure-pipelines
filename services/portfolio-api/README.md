Runnable Java/Maven scaffold for the portfolio-api migration demo.
It provides a small portfolio model with value and weight calculations.
Run `mvn -B -DskipTests=false package` from this directory.
Needs a JDK 17 or newer and Maven 3.8+. Maven must run on a full JDK: if `mvn -v` shows a JRE or older Java, set `JAVA_HOME` to the JDK (compiling fails with "release version 17 not supported" otherwise).
