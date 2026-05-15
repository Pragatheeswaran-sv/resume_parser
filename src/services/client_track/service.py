from typing import Any, Dict, List, Optional
import logging
import datetime
from datetime import timezone
from zoneinfo import ZoneInfo
from src.auth.models import OauthCredentials
from datetime import timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from db.connection import SessionLocal
from sqlalchemy import UUID, String, func, cast, inspect
from sqlalchemy.dialects.postgresql import JSON, aggregate_order_by
from src.admin.models import Admin, Users, ExtractionConfig, ist_now
from src.auth.jwt import create_access_token, hash_password, verify_password
from fastapi import status
from src.client_track.models import InterviewRounds
from src.utils.helper import encrypt_data, decrypt_data

load_dotenv()
logger = logging.getLogger(__name__)

db = SessionLocal()

def rounds():
    try:
        interview_round = db.query(InterviewRounds).filter(InterviewRounds.is_active == True).all()
        return{
            "status": status.HTTP_200_OK,
            "message": "interview rounds retrieved successfully",
            
            "data" : [{
                "round_id" : str(round.round_id),
                "round_name" : round.round_name,
                "created_by" : round.created_by,
                "updated_by" : round.updated_by,
                "is_active" : round.is_active
            }
            for round in interview_round]
        }
    except Exception as e:
        return e
    finally:
        db.close()
    
def add_round(payload, user_name):
    try:
        round_name = payload.get("round_name") if payload.get("round_name") else None
        print('round_name', round_name)
        interview_round = db.query(InterviewRounds).filter(InterviewRounds.round_name == round_name ,InterviewRounds.is_active == True).first()
        if interview_round:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "round already exists",
            }
        interview_round = InterviewRounds(round_name = round_name, created_by = user_name, updated_by = user_name)
        db.add(interview_round)
        db.commit()
        db.refresh(interview_round)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "interview rounds created successfully",
            "data" : {
                "round_id" : str(interview_round.round_id),
                "round_name" : interview_round.round_name,
                "created_by" : interview_round.created_by,
                "updated_by" : interview_round.updated_by,
                "is_active" : interview_round.is_active
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()

def update_round(payload, round_id, user_name):
    try:
        round_name = payload.get("round_name") if payload.get("round_name") else None
        if not round_id:
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Provide interview round id",
            }
        interview_round = db.query(InterviewRounds).filter(InterviewRounds.round_id == round_id ,InterviewRounds.is_active == True).first()
        if interview_round == None:
            return{
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Interview round not found",
            }
        if interview_round.round_name == round_name:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "round already exists",
            }
        interview_round.round_name = round_name
        interview_round.updated_by = user_name
        db.add(interview_round)
        db.commit()
        db.refresh(interview_round)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "interview rounds updated successfully",
            "data" : {
                "round_id" : str(interview_round.round_id),
                "round_name" : interview_round.round_name,
                "created_by" : interview_round.created_by,
                "updated_by" : interview_round.updated_by,
                "is_active" : interview_round.is_active
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()

def delete_round(round_id, user_name):
    try:
        if not round_id:
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Provide interview round id",
            }
        interview_round = db.query(InterviewRounds).filter(InterviewRounds.round_id == round_id ,InterviewRounds.is_active == True).first()
        if interview_round == None:
            return{
                "status": status.HTTP_404_NOT_FOUND,
                "message": "Interview round not found",
            }
        
        interview_round.is_active = False
        interview_round.updated_by = user_name
        db.add(interview_round)
        db.commit()
        db.refresh(interview_round)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "interview rounds deleted successfully",
            "data" : {
                "round_id" : str(interview_round.round_id),
                "round_name" : interview_round.round_name,
                "created_by" : interview_round.created_by,
                "updated_by" : interview_round.updated_by,
                "is_active" : interview_round.is_active
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()