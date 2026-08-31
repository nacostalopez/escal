"""Tests for Fernet encryption of stored credentials."""
import pytest
from cryptography.fernet import InvalidToken

from app.security import encrypt_secret, decrypt_secret
from app.models import StoreCredential


class TestEncryption:
    """Test encryption and decryption of secrets."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypted secrets decrypt to original value."""
        original = "test_secret_token_xyz123"
        
        encrypted = encrypt_secret(original)
        decrypted = decrypt_secret(encrypted)
        
        assert decrypted == original
        assert encrypted != original

    def test_encrypted_value_not_plaintext(self):
        """Test that encrypted value is not the plaintext."""
        original = "sensitive_data"
        encrypted = encrypt_secret(original)
        
        # Encrypted should be different from original
        assert encrypted != original
        # Encrypted should contain URL-safe characters (Fernet)
        assert isinstance(encrypted, str)
        assert "=" in encrypted or "-" in encrypted or "_" in encrypted

    def test_multiple_encryptions_produce_different_ciphertexts(self):
        """Test that same value encrypted multiple times produces different ciphertexts."""
        original = "test_value"
        
        encrypted1 = encrypt_secret(original)
        encrypted2 = encrypt_secret(original)
        
        # Due to Fernet's IV, each encryption should be different
        assert encrypted1 != encrypted2
        # But both should decrypt to the same value
        assert decrypt_secret(encrypted1) == original
        assert decrypt_secret(encrypted2) == original

    def test_decrypt_invalid_token_raises_error(self):
        """Test that decrypting invalid data raises an error."""
        with pytest.raises(InvalidToken):
            decrypt_secret("not_a_valid_fernet_token")

    def test_credentials_stored_encrypted_in_db(self, test_db_session, test_store):
        """Test that credentials are stored encrypted in the database."""
        from uuid import uuid4
        
        # Create credential with plaintext token
        plaintext_token = "shopify_access_token_abc123"
        encrypted_token = encrypt_secret(plaintext_token)
        
        credential = StoreCredential(
            id=uuid4(),
            store_id=test_store.id,
            provider="shopify",
            access_token=encrypted_token,
            refresh_token=encrypt_secret("refresh_token_xyz"),
        )
        test_db_session.add(credential)
        test_db_session.commit()
        
        # Query from database - raw value should be encrypted
        raw_credential = test_db_session.query(StoreCredential).filter_by(id=credential.id).first()
        
        assert raw_credential is not None
        assert raw_credential.access_token != plaintext_token
        assert raw_credential.access_token == encrypted_token
        
        # But when decrypted, should match original
        decrypted_token = decrypt_secret(raw_credential.access_token)
        assert decrypted_token == plaintext_token

    def test_refresh_token_encryption(self, test_db_session, test_store):
        """Test that refresh tokens are also encrypted."""
        from uuid import uuid4
        
        plaintext_refresh = "shopify_refresh_token_xyz789"
        encrypted_refresh = encrypt_secret(plaintext_refresh)
        
        credential = StoreCredential(
            id=uuid4(),
            store_id=test_store.id,
            provider="shopify",
            access_token=encrypt_secret("access_token"),
            refresh_token=encrypted_refresh,
        )
        test_db_session.add(credential)
        test_db_session.commit()
        
        raw_credential = test_db_session.query(StoreCredential).filter_by(id=credential.id).first()
        
        assert raw_credential.refresh_token != plaintext_refresh
        assert decrypt_secret(raw_credential.refresh_token) == plaintext_refresh
