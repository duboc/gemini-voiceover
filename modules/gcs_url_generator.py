import logging
from datetime import timedelta
from typing import Optional
import google.auth
from google.cloud import storage
from google.oauth2 import credentials as oauth2_credentials
from google.oauth2 import service_account
from google.auth import compute_engine
from google.auth import impersonated_credentials
import google.auth.transport.requests

logger = logging.getLogger(__name__)


def get_signed_url(bucket_name: str, blob_name: str, expiration: int = 3600) -> str:
    """
    Generate signed URL for accessing private bucket objects
    
    Handles different credential types:
    - OAuth2 (gcloud auth application-default login)
    - Service Account (JSON key file)
    - Compute Engine (Cloud Run, GCE)
    - Impersonated credentials
    
    Args:
        bucket_name: GCS bucket name
        blob_name: Object path within bucket
        expiration: URL expiration time in seconds (default: 1 hour)
        
    Returns:
        Accessible URL for the GCS object
    """
    try:
        credentials, project = google.auth.default()
        storage_client = storage.Client(credentials=credentials)
        
        # If using OAuth credentials (local development with gcloud auth)
        if isinstance(credentials, oauth2_credentials.Credentials):
            logger.info("Using OAuth2 credentials for GCS access")
            url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
            if credentials.token:
                url = f"{url}?access_token={credentials.token}"
                logger.debug("Generated OAuth2 access token URL")
            else:
                logger.warning("OAuth2 credentials have no token, using direct URL")
            return url
            
        # If using Compute Engine credentials (Cloud Run)
        elif isinstance(credentials, compute_engine.Credentials):
            logger.info("Using Compute Engine credentials for GCS access")
            try:
                # First try to generate a signed URL
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=expiration),
                    method="GET"
                )
                logger.debug("Generated signed URL with Compute Engine credentials")
                return signed_url
            except Exception as e:
                logger.warning(f"Falling back to token auth for Compute Engine: {str(e)}")
                # Fall back to token auth if signing fails
                try:
                    credentials = compute_engine.IDTokenCredentials(
                        credentials, "https://storage.googleapis.com"
                    )
                    url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
                    if credentials.token:
                        url = f"{url}?access_token={credentials.token}"
                        logger.debug("Generated token-based URL for Compute Engine")
                    return url
                except Exception as token_error:
                    logger.error(f"Token-based access also failed: {str(token_error)}")
                    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
            
        # If using service account credentials
        elif isinstance(credentials, service_account.Credentials):
            logger.info("Using Service Account credentials for GCS access")
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            try:
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=expiration),
                    method="GET"
                )
                logger.debug("Generated signed URL with Service Account credentials")
                return signed_url
            except Exception as e:
                logger.warning(f"Signed URL generation failed with Service Account, using direct access: {str(e)}")
                return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
                
        # If using impersonated credentials
        elif isinstance(credentials, impersonated_credentials.Credentials):
            logger.info("Using Impersonated credentials for GCS access")
            try:
                # Try to use the credentials token directly
                headers = {}
                auth_req = google.auth.transport.requests.Request()
                credentials.refresh(auth_req)
                credentials.apply(headers)
                
                if 'authorization' in headers:
                    token = headers['authorization'].split(' ')[1]
                    url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}?access_token={token}"
                    logger.debug("Generated token-based URL for Impersonated credentials")
                    return url
                else:
                    logger.warning("No authorization header found in impersonated credentials")
                    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
                    
            except Exception as e:
                logger.error(f"Impersonated credentials access failed: {str(e)}")
                return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
            
        else:
            logger.warning(f"Unsupported credentials type: {type(credentials)}")
            return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
            
    except Exception as e:
        logger.error(f"Error generating GCS URL: {str(e)}")
        return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"


def get_download_url_with_fallback(bucket_name: str, blob_name: str, expiration: int = 3600) -> dict:
    """
    Get download URL with comprehensive fallback information
    
    Args:
        bucket_name: GCS bucket name
        blob_name: Object path within bucket
        expiration: URL expiration time in seconds
        
    Returns:
        Dictionary with URL and metadata:
        {
            'url': str,
            'type': str,  # 'signed_url', 'token_url', 'direct_url'
            'expires_in_seconds': int,
            'requires_auth': bool,
            'error': str (if any)
        }
    """
    try:
        credentials, project = google.auth.default()
        storage_client = storage.Client(credentials=credentials)
        
        # Check if blob exists
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        if not blob.exists():
            return {
                'url': None,
                'type': 'error',
                'expires_in_seconds': 0,
                'requires_auth': False,
                'error': 'File not found in GCS'
            }
        
        # Generate appropriate URL based on credential type
        if isinstance(credentials, service_account.Credentials):
            try:
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=expiration),
                    method="GET"
                )
                return {
                    'url': url,
                    'type': 'signed_url',
                    'expires_in_seconds': expiration,
                    'requires_auth': False,
                    'error': None
                }
            except Exception as e:
                logger.warning(f"Signed URL generation failed: {e}")
                # Fall through to direct URL
        
        # For OAuth2, Compute Engine, or failed Service Account
        if isinstance(credentials, (oauth2_credentials.Credentials, compute_engine.Credentials)):
            try:
                # Refresh credentials to get current token
                auth_req = google.auth.transport.requests.Request()
                credentials.refresh(auth_req)
                
                if hasattr(credentials, 'token') and credentials.token:
                    url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}?access_token={credentials.token}"
                    # OAuth2 tokens typically expire in 1 hour, but we can't know exactly when
                    token_expiry = min(expiration, 3600)  # Cap at 1 hour
                    return {
                        'url': url,
                        'type': 'token_url',
                        'expires_in_seconds': token_expiry,
                        'requires_auth': False,
                        'error': None
                    }
            except Exception as e:
                logger.warning(f"Token-based URL generation failed: {e}")
        
        # Final fallback - direct URL (requires proper bucket permissions)
        url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
        return {
            'url': url,
            'type': 'direct_url',
            'expires_in_seconds': 0,  # No expiration
            'requires_auth': True,  # May require authentication
            'error': 'Using direct URL - may require public bucket or additional authentication'
        }
        
    except Exception as e:
        logger.error(f"Error generating download URL: {str(e)}")
        return {
            'url': None,
            'type': 'error',
            'expires_in_seconds': 0,
            'requires_auth': False,
            'error': str(e)
        }
