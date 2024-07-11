use crate::types::money_pool::MoneyPool;

use crate::types::transaction::{Transaction, TransactionFilter};
use std::collections::HashMap;
use std::error::Error;
use std::fmt::Display;
use std::sync::Arc;
use tokio::sync::Mutex;

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
    async fn add_pool(&mut self, user_id: &str, new_pool: MoneyPool) -> Result<(), StorageError>;

    async fn load_pools(&self, user_id: &str) -> Result<Vec<MoneyPool>, StorageError>;

    async fn load_pool(
        &self,
        user_id: &str,
        pool_id: &str,
    ) -> Result<Option<MoneyPool>, StorageError>;

    async fn add_transaction(
        &mut self,
        user_id: &str,
        transaction: Transaction,
    ) -> Result<(), StorageError>;

    async fn load_transactions(
        &self,
        user_id: &str,
        filter: Option<TransactionFilter>,
        offset: usize,
        count: usize,
    ) -> Result<Vec<Transaction>, StorageError>;
}

// implementations

pub struct InmemoryStorage {
    pools: HashMap<String, Vec<MoneyPool>>,
    transactions: HashMap<String, Vec<Transaction>>,
}

impl InmemoryStorage {
    #[allow(dead_code)]
    pub fn new() -> InmemoryStorage {
        InmemoryStorage {
            pools: HashMap::new(),
            transactions: HashMap::new(),
        }
    }
}

impl Storage for InmemoryStorage {
    async fn add_pool(&mut self, user_id: &str, new_pool: MoneyPool) -> Result<(), StorageError> {
        if !self.pools.contains_key(user_id) {
            self.pools.insert(user_id.to_owned(), Vec::new());
        }
        self.pools
            .get_mut(user_id)
            .ok_or(StorageError {
                reason: "conflict, user id not found".to_owned(),
            })?
            .push(new_pool);
        Ok(())
    }

    async fn load_pools(&self, user_id: &str) -> Result<Vec<MoneyPool>, StorageError> {
        let maybe_pools = self.pools.get(user_id);
        if let Some(pools) = maybe_pools {
            return Ok(pools.iter().cloned().collect());
        } else {
            return Ok(Vec::new());
        }
    }

    async fn load_pool(
        &self,
        user_id: &str,
        pool_id: &str,
    ) -> Result<Option<MoneyPool>, StorageError> {
        Ok(self
            .load_pools(user_id)
            .await?
            .into_iter()
            .find(|mp| mp.id == pool_id))
    }

    async fn add_transaction(
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

    async fn load_transactions(
        &self,
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

    #[tokio::test]
    async fn test_write_read() {
        let mut storage = InmemoryStorage::new();
        let user_id = "onetwothree".to_owned();
        let pool_id = "somepool".to_owned();

        for idx in 0..10 {
            let res = storage
                .add_transaction(
                    &user_id,
                    Transaction::new_regular(
                        100.0,
                        pool_id.clone(),
                        format!("transaciton {}", idx),
                    ),
                )
                .await;
            assert!(res.is_ok())
        }

        let load_res = storage.load_transactions(&user_id, None, 0, 3).await;
        assert!(load_res.is_ok());
        let loaded = load_res.unwrap();
        assert_eq!(loaded.len(), 3);
    }
}

// simple inmemory storage wrapped in sync machinery to allow its use in an async web app

#[derive(Clone)]
pub struct SharedInmemoryStorage {
    inner: Arc<Mutex<InmemoryStorage>>,
}

impl SharedInmemoryStorage {
    pub fn new() -> SharedInmemoryStorage {
        SharedInmemoryStorage {
            inner: Arc::new(Mutex::new(InmemoryStorage::new())),
        }
    }
}

impl Storage for SharedInmemoryStorage {
    async fn add_pool(&mut self, user_id: &str, new_pool: MoneyPool) -> Result<(), StorageError> {
        self.inner.lock().await.add_pool(user_id, new_pool).await
    }
    async fn load_pool(
        &self,
        user_id: &str,
        pool_id: &str,
    ) -> Result<Option<MoneyPool>, StorageError> {
        self.inner.lock().await.load_pool(user_id, pool_id).await
    }

    async fn load_pools(&self, user_id: &str) -> Result<Vec<MoneyPool>, StorageError> {
        self.inner.lock().await.load_pools(user_id).await
    }
    async fn add_transaction(
        &mut self,
        user_id: &str,
        transaction: Transaction,
    ) -> Result<(), StorageError> {
        self.inner
            .lock()
            .await
            .add_transaction(user_id, transaction)
            .await
    }

    async fn load_transactions(
        &self,
        user_id: &str,
        filter: Option<TransactionFilter>,
        offset: usize,
        count: usize,
    ) -> Result<Vec<Transaction>, StorageError> {
        self.inner
            .lock()
            .await
            .load_transactions(user_id, filter, offset, count)
            .await
    }
}
