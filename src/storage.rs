use chrono::{DateTime, Utc};

use crate::types::transaction::{Transaction, TransactionFilter};
use std::collections::HashMap;
use std::error::Error;
use std::fmt::Display;

#[derive(Debug)]
pub struct StorageError {
    pub reason: String,
}

impl Display for StorageError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Storage error, reason: {}", self.reason)
    }
}

impl Error for StorageError {}

pub trait Storage {
    fn save_transaction(
        &mut self,
        user_id: &str,
        transaction: Transaction,
    ) -> Result<(), StorageError>;

    fn load_transactions(
        &mut self,
        user_id: &str,
        filter: Option<TransactionFilter>,
        offset: usize,
        count: usize,
    ) -> Result<Vec<Transaction>, StorageError>;
}

// implementations

struct InmemoryStorage {
    transactions: HashMap<String, Vec<Transaction>>,
}

impl InmemoryStorage {
    pub fn new() -> InmemoryStorage {
        InmemoryStorage {
            transactions: HashMap::new(),
        }
    }
}

impl Storage for InmemoryStorage {
    fn save_transaction(
        &mut self,
        user_id: &str,
        transaction: Transaction,
    ) -> Result<(), StorageError> {
        if !self.transactions.contains_key(user_id) {
            self.transactions.insert(user_id.to_owned(), Vec::new());
        }
        let user_transactions = self.transactions.get_mut(user_id).ok_or(StorageError {
            reason: "conflict, user id not found".to_owned(),
        })?;
        user_transactions.push(transaction);
        user_transactions.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));
        Ok(())
    }

    fn load_transactions(
        &mut self,
        user_id: &str,
        filter: Option<TransactionFilter>,
        offset: usize,
        count: usize,
    ) -> Result<Vec<Transaction>, StorageError> {
        let user_transactions = self.transactions.get(user_id);
        if let Some(user_transactions) = user_transactions {
            let tf = filter.unwrap_or(TransactionFilter::default());
            Ok(user_transactions
                .iter()
                .rev()
                .filter(|t| tf.matches(t))
                .skip(offset)
                .take(count)
                .map(|t| t.clone())
                .collect::<Vec<Transaction>>())
        } else {
            Ok(Vec::new())
        }
    }
}

#[cfg(test)]
mod inmemory_storage_tests {
    use super::*;

    #[test]
    fn test_write_read() {
        let mut storage = InmemoryStorage::new();
        let user_id = "onetwothree".to_owned();
        let pool_id = "somepool".to_owned();

        for idx in 0..10 {
            let res = storage.save_transaction(
                &user_id,
                Transaction::new_regular(100.0, pool_id.clone(), format!("transaciton {}", idx)),
            );
            assert!(res.is_ok())
        }

        let load_res = storage.load_transactions(&user_id, None, 0, 3);
        assert!(load_res.is_ok());
        let loaded = load_res.unwrap();
        assert_eq!(loaded.len(), 3);
    }
}
