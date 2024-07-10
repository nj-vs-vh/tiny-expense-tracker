use crate::types::currency::Currency;
use serde::{Deserialize, Serialize};

// main struct for modelling bank account / savings / pile of cash
#[derive(Deserialize, Serialize)]
pub struct MoneyPool {
    id: String,
    display_name: String,
    currency: Currency,
    balance: f32,
}
