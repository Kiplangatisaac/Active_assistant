use keyring::Entry;
use rand::RngCore;

const SERVICE_NAME: &str = "ActiveAssistantDaemon";
const KEY_NAME: &str = "db_encryption_key";

/// Generate a 256-bit (256 bit = 32 bytes) random hex key
pub fn generate_secure_hex_key() -> String {
    let mut key_bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut key_bytes);
    hex::encode(key_bytes)
}

/// Get existing key from OS keyring, or generate and store a new one
pub fn get_or_create_db_key() -> Result<String, Box<dyn std::error::Error>> {
    let entry = Entry::new(SERVICE_NAME, KEY_NAME)?;

    match entry.get_password() {
        Ok(existing_key) => Ok(existing_key),
        Err(keyring::Error::NoEntry) => {
            let new_key = generate_secure_hex_key();
            entry.set_password(&new_key)?;
            println!("[Security] New 256-bit database encryption key generated in OS vault.");
            Ok(new_key)
        }
        Err(e) => Err(Box::new(e)),
    }
}

/// Update the stored key in the OS secure vault
pub fn update_stored_db_key(new_key: &str) -> Result<(), Box<dyn std::error::Error>> {
    let entry = Entry::new(SERVICE_NAME, KEY_NAME)?;
    entry.set_password(new_key)?;
    Ok(())
}