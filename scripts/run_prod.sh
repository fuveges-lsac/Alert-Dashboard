#!/bin/bash
cd backend
mkdir -p logs
source venv/bin/activate
gunicorn app.main:app -c gunicorn.conf.py
