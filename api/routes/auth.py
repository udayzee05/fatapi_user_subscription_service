from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from api.models.user import Token
from api.core.db import db
from api.core.oauth2 import create_access_token,oauth2_scheme
from api.core.utils import verify_password
from datetime import datetime, timezone
import logging

router = APIRouter(prefix="/login", tags=["Authentication"])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("", response_model=Token, status_code=status.HTTP_200_OK)
async def login(user_credentials: OAuth2PasswordRequestForm = Depends()):
    # Fetch user from the database
    user = await db["users"].find_one({
        "$or": [{"name": user_credentials.username}, {"email": user_credentials.username}]
    })

    if not user or not verify_password(user_credentials.password, user["password"]):
        logger.warning("Invalid credentials for user: %s", user_credentials.username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid username or password"
        )

    # Check for active subscription
    user_id = user["_id"]
    subscriptions = await db["subscriptions"].find({"user_id": user_id}).to_list(length=None)
    subscription_active = any(sub["status"] == "active" for sub in subscriptions)

    # Calculate remaining trial days (if applicable)
    now = datetime.now(timezone.utc)
    trial_end = user.get("trial_end_date")
    days_remaining_in_trial = 0

    if trial_end:
        trial_end_date = trial_end.replace(tzinfo=timezone.utc)
        if now <= trial_end_date:
            days_remaining_in_trial = (trial_end_date - now).days

    # Create access token
    access_token = create_access_token(data={"id": str(user_id)})

    logger.info("User %s logged in successfully", user_credentials.username)

    # Return response with subscription status and trial days remaining
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "subscription_active": subscription_active,
        "days_remaining_in_trial": days_remaining_in_trial
    }
@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(token: str = Depends(oauth2_scheme)):
    """Logout user and blacklist the JWT token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or missing token"
        )

    # Blacklist the token
    await db["blacklist_token"].insert_one({"token": token})

    logging.info(f"Token blacklisted: {token}")
    return {"detail": "Successfully logged out"}



# @router.get("/check-token", status_code=status.HTTP_200_OK)
# async def check_token(request: Request):
#     """Check if the token is valid or blacklisted."""
#     token = request.headers.get("Authorization")
#     if not token or not token.startswith("Bearer "):
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Invalid or missing token"
#         )

#     token = token.split(" ")[1]
#     # Check if the token is blacklisted
#     blacklisted = await db["blacklist_token"].find_one({"token": token})
#     if blacklisted:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Token has been invalidated. Please log in again."
#         )

#     return {"detail": "Token is valid"}