fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}

fn main() {
    println!("{}", greet("Mac"));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn greets_name() {
        assert_eq!(greet("Mac"), "Hello, Mac!");
    }
}
