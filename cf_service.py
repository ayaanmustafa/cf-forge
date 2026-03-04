import requests
from datetime import datetime
from bs4 import BeautifulSoup
from fastapi import HTTPException
CF_API_URL = "https://codeforces.com/api/user.status"

def fetch_solved_problems(handle: str):
    try:
        response = requests.get(
            CF_API_URL,
            params={"handle": handle},
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="CF API timeout")
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="CF API request failed")

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid response from CF")

    if data.get("status") != "OK":
        raise HTTPException(status_code=404, detail="Invalid CF handle")

    solved = {}

    for submission in data["result"]:
        if submission["verdict"] == "OK":
            problem = submission["problem"]

            key = (problem["contestId"], problem["index"])

            # Keep earliest accepted submission
            if key not in solved:
                solved[key] = {
                    "contest_id": problem["contestId"],
                    "index": problem["index"],
                    "name": problem["name"],
                    "rating": problem.get("rating"),
                    "solved_at": datetime.utcfromtimestamp(
                        submission["creationTimeSeconds"]
                    ),
                    "submission_id": submission["id"]
                }

    return list(solved.values())


def fetch_all_problems(min_rating=None, max_rating=None):
    """Fetch all problems from Codeforces problemset"""
    try:
        response = requests.get(
            "https://codeforces.com/api/problemset.problems",
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="CF API timeout")
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="CF API request failed")

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid response from CF")

    if data.get("status") != "OK":
        raise HTTPException(status_code=502, detail="Failed to fetch problems")

    problems = []
    for problem in data.get("result", {}).get("problems", []):
        rating = problem.get("rating")
        
        # Filter by rating if specified
        if min_rating and rating and rating < min_rating:
            continue
        if max_rating and rating and rating > max_rating:
            continue

        problems.append({
            "contest_id": problem["contestId"],
            "index": problem["index"],
            "name": problem["name"],
            "rating": rating
        })

    return problems

def fetch_submission_code(contest_id: int, submission_id: int):
    try:
        url = f"https://codeforces.com/contest/{contest_id}/submission/{submission_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")

    code_block = soup.find("pre", {"id": "program-source-text"})
    if not code_block:
        return None

    return code_block.text