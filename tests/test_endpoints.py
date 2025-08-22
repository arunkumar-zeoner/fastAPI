import pytest
from fastapi.testclient import TestClient
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.main import app

client = TestClient(app)

def test_authorize_endpoint():
    """Test the authorize endpoint"""
    payload = {
        "request": {
            "userAttributes": {
                "custom:token": "gIkTNkQ3lW7Nyx5x1cO3uI9MH3-pcg27DO9Vc9E0gniTkJLJ",
                "site": "dev"
            }
        }
    }
    
    response = client.post("/authorize", json=payload)
    assert response.status_code in [200, 401]

def test_patient_details_endpoint():
    """Test the patient-details endpoint"""
    headers = {
        "Authorization": "eyJraWQiOiJ2bURTYjVuemNJRDFxU1RsdExhdml6N0pKMzlJaVlkSkg5eGxGTTNpMjVZPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiIxNDQ4NTQ3OC0zMDExLTcwMzMtZjk5Yi0zZTUyNTA0MzhkNjUiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6XC9cL2NvZ25pdG8taWRwLnVzLWVhc3QtMS5hbWF6b25hd3MuY29tXC91cy1lYXN0LTFfYTNrNFF2VWMzIiwiY29nbml0bzp1c2VybmFtZSI6IjE0NDg1NDc4LTMwMTEtNzAzMy1mOTliLTNlNTI1MDQzOGQ2NSIsIm9yaWdpbl9qdGkiOiJmMmM5MjNlMS0zNjdlLTQ1YTEtOWRjMC1jOWEwMDQ0MTc4ZDgiLCJhdWQiOiJramRkaTFib2ZwdjN0bW90aGIxbTc1MXY2IiwiY3VzdG9tOnNpdGUiOiJkZXYiLCJldmVudF9pZCI6ImExZmUxNTViLTlhYjYtNDZiMC1iNTdlLTBlMGJkNjcyM2M4YiIsInRva2VuX3VzZSI6ImlkIiwiYXV0aF90aW1lIjoxNzU1ODQ1NDc4LCJleHAiOjE3NTU4NDkwNzgsImlhdCI6MTc1NTg0NTQ3OCwianRpIjoiY2IwZGVmYmMtNjgyZC00ZDI0LTkzNjktOWE4NGFmOWEzZjBhIiwiZW1haWwiOiJwcmFrYXNoQHplb25lci5jb20ifQ.jsp9yPYN_ccfRJ7pvgHDS5egEM-b1HKh954SwVhdN1eqICgPe07wN1qLarOeCeYpKUjnIwmunD9xOuYLXOV7cCRZXOQKcbxXv11isyD4olVSy-PTgAXgZ2NY6kgqg9N-8lrKIlxe49Y6jksKUZhC-Tf5nRbz6MjKv_vWSNOCIT0UbZ65himtND5o4pLoxHpxBDV8CaSjFdqb9-nO9rtgygg-uPoDhLiUnHaz7rd4w28RKUHNJyvmradp2bvdP8XksxNT0MVEU5GEDm44B80VNBqRMDATwWeYk00WOH1Ammvhk6Ukxm8BJedh3JYi-yyM2dZOJc1_cWR6EJHRvZYCvA",
        "Content-Type": "application/json"
    }
    
    payload = {
        "site": "dev",
        "page": 1,
        "page_size": 5,
        "email": "prakash@zeoner.com"
    }
    
    response = client.post("/patient-details", json=payload, headers=headers)
    assert response.status_code in [200, 401]