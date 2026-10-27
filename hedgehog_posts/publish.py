"""Post finished images to Instagram (Graph API) and a LinkedIn company page."""

import os
import re
import time

import requests


class Instagram:
    """Instagram Graph API publisher. Images must be at public URLs."""

    def __init__(self):
        self.user_id = os.environ["IG_USER_ID"]
        self.token = os.environ["IG_ACCESS_TOKEN"]
        host = os.environ.get("IG_GRAPH_HOST") or "graph.facebook.com"
        version = os.environ.get("IG_GRAPH_VERSION") or "v23.0"
        self.base = f"https://{host}/{version}"

    def _publish(self, params):
        params["access_token"] = self.token
        resp = requests.post(f"{self.base}/{self.user_id}/media", data=params, timeout=60)
        resp.raise_for_status()
        container = resp.json()["id"]

        # Instagram fetches and processes the image asynchronously.
        for _ in range(30):
            status = requests.get(f"{self.base}/{container}", timeout=30, params={
                "fields": "status_code", "access_token": self.token}).json()
            if status.get("status_code") == "FINISHED":
                break
            if status.get("status_code") == "ERROR":
                raise RuntimeError(f"Instagram could not process the image: {status}")
            time.sleep(5)

        resp = requests.post(f"{self.base}/{self.user_id}/media_publish", timeout=60, data={
            "creation_id": container, "access_token": self.token})
        resp.raise_for_status()
        return resp.json()["id"]

    def post_image(self, image_url, caption):
        return self._publish({"image_url": image_url, "caption": caption})

    def post_story(self, image_url):
        return self._publish({"image_url": image_url, "media_type": "STORIES"})


# LinkedIn "little text" treats these characters as markup.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")


def linkedin_text(text, hashtags):
    escaped = _RESERVED.sub(r"\\\1", text)
    tags = " ".join("{hashtag|\\#|%s}" % tag for tag in hashtags)
    return f"{escaped}\n\n{tags}" if tags else escaped


class LinkedIn:
    """Posts an image to a LinkedIn organization page via the Posts API."""

    def __init__(self):
        self.token = os.environ["LINKEDIN_ACCESS_TOKEN"]
        self.author = f"urn:li:organization:{os.environ['LINKEDIN_ORG_ID']}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "LinkedIn-Version": os.environ.get("LINKEDIN_API_VERSION") or "202509",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def post_image(self, image_path, commentary, alt_text):
        resp = requests.post("https://api.linkedin.com/rest/images?action=initializeUpload",
                             headers=self.headers, timeout=60,
                             json={"initializeUploadRequest": {"owner": self.author}})
        resp.raise_for_status()
        upload = resp.json()["value"]
        with open(image_path, "rb") as f:
            put = requests.put(upload["uploadUrl"], data=f, timeout=120,
                               headers={"Authorization": f"Bearer {self.token}"})
        put.raise_for_status()

        resp = requests.post("https://api.linkedin.com/rest/posts", headers=self.headers, timeout=60, json={
            "author": self.author,
            "commentary": commentary,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "content": {"media": {"id": upload["image"], "altText": alt_text[:4000]}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        })
        resp.raise_for_status()
        return resp.headers.get("x-restli-id", "")
