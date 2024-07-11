use rusty_money::iso::{find, Currency as rmCurrency};
use serde::de::{self, Error, Unexpected, Visitor};
use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(PartialEq, Eq, Debug)]
pub struct Currency {
    // wrapping rusty money Currency type to make it (de)serializable
    pub rmc: rmCurrency,
}

impl Currency {
    pub fn new(rmc: &rmCurrency) -> Currency {
        return Currency { rmc: rmc.clone() };
    }
}

impl Serialize for Currency {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.collect_str(self.rmc.iso_alpha_code)
    }
}

struct CurrencyVisitor;

impl<'de> Visitor<'de> for CurrencyVisitor {
    type Value = Currency;

    fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
        formatter.write_str("a 3-letter ISO-4217 currency code")
    }

    fn visit_str<E>(self, v: &str) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        find(&v.to_owned().to_uppercase())
            .map(|rmc| Currency { rmc: *rmc })
            .ok_or(Error::invalid_value(Unexpected::Str(v), &self))
    }
}

impl<'de> Deserialize<'de> for Currency {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        deserializer.deserialize_str(CurrencyVisitor)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusty_money::iso;

    #[test]
    fn dump_currency() {
        let c = Currency::new(iso::AMD);
        assert_eq!(serde_json::to_string(&c).unwrap(), "\"AMD\"");
    }

    #[test]
    fn parse_currency() {
        let parsed = serde_json::from_str::<Currency>("\"EUR\"");
        assert!(parsed.is_ok());
        if let Ok(curr) = parsed {
            assert_eq!(
                curr,
                Currency {
                    rmc: iso::EUR.to_owned()
                }
            );
        }
    }

    #[test]
    fn list_of_currencies() {
        let original = vec![iso::AMD, iso::USD, iso::UAH, iso::EUR, iso::GEL]
            .into_iter()
            .map(|c| Currency::new(c))
            .collect::<Vec<Currency>>();
        let dump_res = serde_json::to_string(&original);
        assert!(dump_res.is_ok());
        let load_res = serde_json::from_str::<Vec<Currency>>(&dump_res.unwrap());
        assert!(load_res.is_ok());
        assert_eq!(load_res.unwrap(), original)
    }
}
