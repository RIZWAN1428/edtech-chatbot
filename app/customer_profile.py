"""
Mock customer profile 'API'.

In a real system this would call an internal CRM/customer DB service.
Here it's a small in-memory mock so the bonus 'personalization' requirement
can be demonstrated without needing real infrastructure.
"""

MOCK_CUSTOMERS = {
    "user_101": {
        "user_id": "user_101",
        "name": "Aditi Sharma",
        "plan": "Pro",
        "enrolled_courses": ["Python for Beginners", "Data Structures Basics"],
        "member_since": "2024-03-12",
    },
    "user_102": {
        "name": "Rohit Verma",
        "user_id": "user_102",
        "plan": "Basic",
        "enrolled_courses": ["Intro to Web Development"],
        "member_since": "2025-01-05",
    },
    "user_103": {
        "user_id": "user_103",
        "name": "Sneha Iyer",
        "plan": "Premium",
        "enrolled_courses": ["Machine Learning 101", "SQL Mastery", "System Design"],
        "member_since": "2023-11-20",
    },
}


def get_customer_profile(user_id: str) -> dict | None:
    return MOCK_CUSTOMERS.get(user_id)


def personalize_greeting(user_id: str | None) -> str:
    if not user_id:
        return "Hi! Welcome to EduSpark Support. How can I help you today?"
    profile = get_customer_profile(user_id)
    if not profile:
        return "Hi! Welcome to EduSpark Support. How can I help you today?"
    return (
        f"Hi {profile['name']}! Welcome back to EduSpark Support. "
        f"I see you're on the {profile['plan']} plan. How can I help you today?"
    )
