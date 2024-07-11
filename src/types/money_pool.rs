use crate::types::currency::Currency;
use serde::{Deserialize, Serialize};

// main struct for modelling bank account / savings / pile of cash
#[derive(Deserialize, Serialize, Clone)]
pub struct MoneyPool {
    pub id: String,
    pub display_name: String,
    pub currency: Currency,
    pub balance: f32,
}
