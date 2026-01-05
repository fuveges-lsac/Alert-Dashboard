#!/bin/bash
cd backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info
