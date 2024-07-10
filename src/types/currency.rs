use rusty_money::iso::{find, Currency as rmCurrency};
use serde::de::{self, Error, Unexpected, Visitor};
use serde::{Deserialize, Serialize};
use std::fmt;

pub struct Currency {
    // wrapping rusty money Currency type to make it (de)serializable
    pub rmc: rmCurrency,
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
        find(v)
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
