from typing import Any, Dict, List, Optional
import logging
import datetime
from datetime import timezone
from zoneinfo import ZoneInfo
from src.candidate.models import Candidate
from src.resume_filter.models import Resume
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
from src.client_track.models import CandidateInterviews, Clients, InterviewRounds, InterviewStatus
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
        round_name = payload.get("round_name") or None
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
        round_name = payload.get("round_name") or None
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

def view_clients():
    try:
        clients = db.query(Clients).filter(Clients.is_active == True).all()
        return{
            "status": status.HTTP_200_OK,
            "message": "clients retrieved successfully",
            
            "data" : [{
                "client_id" : str(client.client_id),
                "company_name" : client.company_name,
                "contact_person" : client.contact_person,
                "location" : client.location,
                "email_address" : client.email_address,
                "phone_number" : client.phone_number,
                "created_by" : client.created_by,
                "updated_by" : client.updated_by,
                "is_active" : client.is_active,
            }
            for client in clients]
        }
    except Exception as e:
        return e
    finally:
        db.close()

def add_client(payload, user_name):
    try:
        company_name = payload.get("company_name") or None
        contact_person = payload.get("contact_person") or None
        location = payload.get("location") or None
        email_address = payload.get("email_address") or None
        phone_number = payload.get("phone_number") or None

        client = db.query(Clients).filter(Clients.email_address == email_address, Clients.phone_number == phone_number, Clients.is_active == True).first()
        if client:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "client already exists",
            }
        if company_name == None or contact_person == None or location == None or email_address == None or phone_number == None:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "enter values to add client",
            }
        new_client = Clients(company_name = company_name, contact_person = contact_person, location = location, email_address = email_address, phone_number = phone_number, created_by = user_name, updated_by = user_name)
        db.add(new_client)
        db.commit()
        db.refresh(new_client)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "client created successfully",
            "data" : {
                "client_id" : str(new_client.client_id),
                "company_name" : new_client.company_name,
                "contact_person" : new_client.contact_person,
                "location" : new_client.location,
                "email_address" : new_client.email_address,
                "phone_number" : new_client.phone_number,
                "created_by" : new_client.created_by,
                "updated_by" : new_client.updated_by,
                "is_active" : new_client.is_active
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()

def modify_client(payload, client_id, user_name):
    try:
        
        if not client_id:
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Provide client id",
            }
        client = db.query(Clients).filter(Clients.client_id == client_id ,Clients.is_active == True).first()
        if client == None:
            return{
                "status": status.HTTP_404_NOT_FOUND,
                "message": "client not found",
            }
        
        company_name = payload.get("company_name") or client.company_name
        contact_person = payload.get("contact_person") or client.contact_person
        location = payload.get("location") or client.location
        email_address = payload.get("email_address") or client.email_address
        phone_number = payload.get("phone_number") or client.phone_number

        if company_name == None or contact_person == None or location == None or email_address == None or phone_number == None:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "enter values to update client",
            }

        if client.company_name == company_name and client.contact_person == contact_person and client.location == location and client.email_address == email_address and client.phone_number == phone_number:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "client already exists",
            }
        client.company_name = company_name
        client.contact_person = contact_person
        client.location = location
        client.email_address = email_address
        client.phone_number = phone_number
        client.updated_by = user_name
        
        db.add(client)
        db.commit()
        db.refresh(client)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "client updated successfully",
            "data" : {
                "client_id" : str(client.client_id),
                "company_name" : client.company_name,
                "contact_person" : client.contact_person,
                "location" : client.location,
                "email_address" : client.email_address,
                "phone_number" : client.phone_number,
                "created_by" : client.created_by,
                "updated_by" : client.updated_by,
                "is_active" : client.is_active
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()

def remove_client(client_id, user_name):
    try:
        if not client_id:
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Provide client id",
            }
        client = db.query(Clients).filter(Clients.client_id == client_id ,Clients.is_active == True).first()
        if client == None:
            return{
                "status": status.HTTP_404_NOT_FOUND,
                "message": "client not found",
            }
        
        client.is_active = False
        client.updated_by = user_name
        db.add(client)
        db.commit()
        db.refresh(client)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "client deleted successfully",
            "data" : {
                "client_id" : str(client.client_id),
                "company_name" : client.company_name,
                "contact_person" : client.contact_person,
                "location" : client.location,
                "email_address" : client.email_address,
                "phone_number" : client.phone_number,
                "created_by" : client.created_by,
                "updated_by" : client.updated_by,
                "is_active" : client.is_active
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()

def view_interviews():
    try:
        interviews = (
            db.query(CandidateInterviews)
            .join(Resume, Resume.resume_id == CandidateInterviews.resume_id)
            .join(Candidate, Candidate.candidate_id == Resume.candidate_id)
            .filter(CandidateInterviews.is_active == True)
            .all())
        # candidate_name = db.query(Candidate.name).join(Resume, Resume.candidate_id == Candidate.candidate_id).filter(Candidate.is_active == True).all()
        print(interviews)
        # return '1'
        return{
            "status": status.HTTP_200_OK,
            "message": "candidate interviews retrieved successfully",
            "data" : [{
                "interview_id" : str(interview.interview_id),
                "resume_id" : str(interview.resume_id),
                "client_id" : str(interview.client_id),
                "candidate_name" : interview.resume.candidate.name,
                "experience" : interview.experience,
                "status" : interview.status,
                "role" : interview.role,
                "created_by" : interview.created_by,
                "updated_by" : interview.updated_by,
                "is_active" : interview.is_active,
            }
            for interview in interviews]
        }
    except Exception as e:
        return e
    finally:
        db.close()

def add_interview(payload, user_name):
    try:
        resume_id = payload.get("resume_id") or None
        client_id = payload.get("client_id") or None
        experience = payload.get("experience") or None
        Status = payload.get("status") or None
        role = payload.get("role") or None

        client = db.query(CandidateInterviews).filter(CandidateInterviews.resume_id == resume_id, CandidateInterviews.client_id == client_id, CandidateInterviews.is_active == True).first()
        if client:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "Interview already exists",
            }
        if resume_id == None or client_id == None or experience == None or Status == None or role == None:
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "enter values to add interview",
            }
        new_interview = CandidateInterviews(resume_id = resume_id, client_id = client_id, experience = experience, status = Status, role = role, created_by = user_name, updated_by = user_name)
        db.add(new_interview)
        db.commit()
        db.refresh(new_interview)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "client created successfully",
            "data" : {
                "interview_id" : str(new_interview.interview_id),
                "resume_id" : str(new_interview.resume_id),
                "client_id" : str(new_interview.client_id),
                "experience" : new_interview.experience,
                "status" : new_interview.status,
                "role" : new_interview.role,
                "created_by" : new_interview.created_by,
                "updated_by" : new_interview.updated_by,
                "is_active" : new_interview.is_active,
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()

def remove_interview(interview_id, user_name):
    try:
        if not interview_id:
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Provide interview id",
            }
        interview = db.query(CandidateInterviews).filter(CandidateInterviews.interview_id == interview_id ,CandidateInterviews.is_active == True).first()
        if interview == None:
            return{
                "status": status.HTTP_404_NOT_FOUND,
                "message": "interview not found",
            }
        
        interview.is_active = False
        interview.updated_by = user_name
        db.add(interview)
        db.commit()
        db.refresh(interview)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "client deleted successfully",
            "data" : {
                "interview_id" : str(interview.interview_id),
                "resume_id" : str(interview.resume_id),
                "client_id" : str(interview.client_id),
                "experience" : interview.experience,
                "role" : interview.role,
                "status" : interview.status,
                "created_by" : interview.created_by,
                "updated_by" : interview.updated_by,
                "is_active" : interview.is_active
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()

def view_interview_status(interview_id):
    try:
        interview_status = db.query(InterviewStatus).filter(InterviewStatus.interview_id == interview_id, InterviewStatus.is_active == True).order_by(InterviewStatus.created_at).all()
        return{
            "status": status.HTTP_200_OK,
            "message": "candidate interview status retrieved successfully",
            "data" : [{
                "interview_status_id" : str(interview.interview_status_id),
                "interview_id" : str(interview.interview_id),
                "round_id" : str(interview.round_id),
                "round_no" : interview.round_no,
                "scheduled_date" : interview.scheduled_date,
                "meeting_link" : interview.meeting_link,
                "feedback" : interview.feedback,
                "status" : interview.status,
                "created_by" : interview.created_by,
                "updated_by" : interview.updated_by,
                "is_active" : interview.is_active,
            }
            for interview in interview_status]
        }
    except Exception as e:
        return e
    finally:
        db.close()

def add_interview_status(payload, user_name):
    try:
        interview_id = payload.get("interview_id") or None
        round_id = payload.get("round_id") or None
        round_no = payload.get("round_no") or None
        scheduled_date = payload.get("scheduled_date") or None
        meeting_link = payload.get("meeting_link") or None
        feedback = payload.get("feedback") or ""
        Status = payload.get("status") or None
        
        Candidate_interviews = db.query(CandidateInterviews).filter(CandidateInterviews.interview_id == interview_id, CandidateInterviews.is_active == True).first()
        Candidate_status = str(Candidate_interviews.status)
        candidate_status = Candidate_status.split(' ')[-1]
        if Candidate_status.lower() == "rejected":
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "can't schedule interview anymore, candidate rejected last round",
            }
        
        if candidate_status.lower() != "cleared":
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "can't schedule interview, previous round not cleared",
            }

        interview_status = db.query(InterviewStatus).filter(InterviewStatus.round_no == round_no, InterviewStatus.round_id == round_id, InterviewStatus.is_active == True).first()
        if interview_status:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "Interview status already exists",
            }
        if interview_id == None or round_id == None or round_no == None or scheduled_date == None or meeting_link == None or Status == None:
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "enter values to add interview status",
            }
        new_interview_status = InterviewStatus(interview_id = interview_id, round_id = round_id, round_no = round_no, scheduled_date = scheduled_date, meeting_link = meeting_link, feedback = feedback, status = Status, created_by = user_name, updated_by = user_name)
        db.add(new_interview_status)
        db.commit()
        db.refresh(new_interview_status)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "client created successfully",
            "data" : {
                "interview_status_id" : str(new_interview_status.interview_status_id),
                "interview_id" : str(new_interview_status.interview_id),
                "round_id" : str(new_interview_status.round_id),
                "round_no" : str(new_interview_status.round_no),
                "scheduled_date" : new_interview_status.scheduled_date,
                "meeting_link" : new_interview_status.meeting_link,
                "feedback" : new_interview_status.feedback,
                "status" : new_interview_status.status,
                "created_by" : new_interview_status.created_by,
                "updated_by" : new_interview_status.updated_by,
                "is_active" : new_interview_status.is_active,
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()

def modify_interview_status(payload, interview_status_id, user_name):
    try:
        
        if not interview_status_id:
            return{
                "status": status.HTTP_400_BAD_REQUEST,
                "message": "Provide interview status id",
            }
        interview_status = db.query(InterviewStatus).filter(
            InterviewStatus.interview_status_id == interview_status_id,
            InterviewStatus.is_active == True).first()
        if interview_status == None:
            return{
                "status": status.HTTP_404_NOT_FOUND,
                "message": "interview status not found",
            }
        feedback = payload.get("feedback") or interview_status.feedback
        scheduled_date = payload.get("scheduled_date") or interview_status.scheduled_date
        meeting_link = payload.get("meeting_link") or interview_status.meeting_link
        Status = payload.get("status") or interview_status.status

        if scheduled_date == None or meeting_link == None or Status == None:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "enter values to update interview status",
            }

        if interview_status.scheduled_date == scheduled_date and interview_status.meeting_link == meeting_link and interview_status.status == Status and interview_status.feedback == feedback:
            return{
                "status": status.HTTP_208_ALREADY_REPORTED,
                "message": "interview status already exists",
            }
        interview_status.scheduled_date = scheduled_date
        interview_status.feedback = feedback
        interview_status.meeting_link = meeting_link
        interview_status.status = Status
        interview_status.updated_by = user_name
        
        db.add(interview_status)
        db.commit()
        db.refresh(interview_status)

        interview_id = interview_status.interview_id
        Status = str(interview_status.status)
        round_no = interview_status.round_no

        Candidate_interviews = db.query(CandidateInterviews).filter(CandidateInterviews.interview_id == interview_id, CandidateInterviews.is_active == True).first()
        if Status.lower() == "completed":
            Candidate_interviews.status = f"round {round_no} completed"
        elif Status.lower() == "cleared":
            Candidate_interviews.status = f"round {round_no} cleared"
        elif Status.lower() == "rejected":
            Candidate_interviews.status = "rejected"
        
        db.add(Candidate_interviews)
        db.commit()
        db.refresh(Candidate_interviews)

        return{
            "status": status.HTTP_201_CREATED,
            "message": "candidate interview status updated successfully",
            "data" : {
                "interview_status_id" : str(interview_status.interview_status_id),
                "interview_id" : str(interview_status.interview_id),
                "round_id" : str(interview_status.round_id),
                "round_no" : str(interview_status.round_no),
                "scheduled_date" : interview_status.scheduled_date,
                "meeting_link" : interview_status.meeting_link,
                "feedback" : interview_status.feedback,
                "status" : interview_status.status,
                "created_by" : interview_status.created_by,
                "updated_by" : interview_status.updated_by,
                "is_active" : interview_status.is_active,
            }
        }
    except Exception as e:
        return e
    finally:
        db.close()
