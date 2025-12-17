from flask import Flask, jsonify, request
import requests
from urllib.parse import quote_plus
from json import dumps, decoder

import phonenumbers
from phonenumbers.phonenumberutil import region_code_for_country_code
import pycountry

app = Flask(__name__)

OWNER = "@GoatThunder"

# ---------------- HELPERS ----------------

def getUserId(username, sessionid):
    headers = {
        "User-Agent": "iphone_ua",
        "x-ig-app-id": "936619743392459"
    }

    api = requests.get(
        f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
        headers=headers,
        cookies={"sessionid": sessionid},
        timeout=10
    )

    try:
        if api.status_code == 404:
            return {"id": None, "error": "User not found"}

        return {"id": api.json()["data"]["user"]["id"], "error": None}

    except decoder.JSONDecodeError:
        return {"id": None, "error": "Rate limit"}


def getInfo(search, sessionid, searchType="username"):
    if searchType == "username":
        data = getUserId(search, sessionid)
        if data["error"]:
            return {"user": None, "error": data["error"]}
        userId = data["id"]
    else:
        userId = search

    try:
        response = requests.get(
            f"https://i.instagram.com/api/v1/users/{userId}/info/",
            headers={"User-Agent": "Instagram 64.0.0.14.96"},
            cookies={"sessionid": sessionid},
            timeout=10
        )

        if response.status_code == 429:
            return {"user": None, "error": "Rate limit"}

        info_user = response.json().get("user")
        if not info_user:
            return {"user": None, "error": "Not found"}

        info_user["userID"] = userId
        return {"user": info_user, "error": None}

    except requests.exceptions.RequestException:
        return {"user": None, "error": "Request failed"}


def advanced_lookup(username):
    data = "signed_body=SIGNATURE." + quote_plus(
        dumps({"q": username, "skip_recovery": "1"}, separators=(",", ":"))
    )

    api = requests.post(
        "https://i.instagram.com/api/v1/users/lookup/",
        headers={
            "User-Agent": "Instagram 101.0.0.15.120",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data=data,
        timeout=10
    )

    try:
        return {"data": api.json(), "error": None}
    except decoder.JSONDecodeError:
        return {"data": None, "error": "Rate limit"}


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return jsonify({
        "api": "Instagram Lookup API",
        "usage": "/lookup?username=USERNAME&sessionid=SESSION_ID",
        "Owner": OWNER
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "Owner": OWNER
    })


@app.route("/lookup")
def lookup():
    username = request.args.get("username")
    sessionid = request.args.get("sessionid")

    if not username or not sessionid:
        return jsonify({
            "success": False,
            "error": "username and sessionid required",
            "Owner": OWNER
        })

    info = getInfo(username, sessionid)

    if info["error"]:
        return jsonify({
            "success": False,
            "error": info["error"],
            "Owner": OWNER
        })

    user = info["user"]

    phone_info = None
    if user.get("public_phone_number"):
        try:
            number = "+" + str(user["public_phone_country_code"]) + str(user["public_phone_number"])
            pn = phonenumbers.parse(number)
            country = pycountry.countries.get(
                alpha_2=region_code_for_country_code(pn.country_code)
            )
            phone_info = {
                "number": number,
                "country": country.name if country else None
            }
        except:
            pass

    advanced = advanced_lookup(user["username"])

    return jsonify({
        "success": True,
        "user": {
            "username": user.get("username"),
            "userID": user.get("userID"),
            "full_name": user.get("full_name"),
            "biography": user.get("biography"),
            "followers": user.get("follower_count"),
            "following": user.get("following_count"),
            "posts": user.get("media_count"),
            "is_private": user.get("is_private"),
            "is_verified": user.get("is_verified"),
            "external_url": user.get("external_url"),
            "public_email": user.get("public_email"),
            "public_phone": phone_info,
            "profile_pic": user.get("hd_profile_pic_url_info", {}).get("url")
        },
        "advanced_lookup": advanced,
        "Owner": OWNER
    })
