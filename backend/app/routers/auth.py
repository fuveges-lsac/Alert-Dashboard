from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

@router.get("/login")
async def login():
    return {"message": "Redirect to Azure AD"}

@router.get("/callback")
async def auth_callback():
    return RedirectResponse(url="/")

@router.get("/logout")
async def logout():
    return RedirectResponse(url="/")
