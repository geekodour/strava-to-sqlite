import json
import socket
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

import click
import requests
from pydantic import AliasPath, BaseModel, Field, field_validator


def to_epoch(t):
    return int(t.timestamp())


# NOTE: Taken from https://github.com/geodav-tech/decode-google-maps-polyline
# NOTE: Other of lat/lng is reversed in this version for strava polyline
# Also see:
# - https://valhalla.github.io/demos/polyline/
# - https://www.markhneedham.com/blog/2017/04/29/leaflet-strava-polylines-osm/
# - https://github.com/mapbox/polyline
def decode_polyline(polyline_str) -> str:
    """Pass a Strava encoded polyline string; returns list of lat/lon pairs"""
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {"latitude": 0, "longitude": 0}

    while index < len(polyline_str):
        for unit in ["latitude", "longitude"]:
            shift, result = 0, 0

            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if not byte >= 0x20:
                    break

            if result & 1:
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = result >> 1

        lat += changes["latitude"]
        lng += changes["longitude"]

        coordinates.append((lng / 100000.0, lat / 100000.0))

    return json.dumps({"type": "LineString", "coordinates": coordinates})


def ensure_tables(db):
    if "users" not in db.table_names():
        db["users"].create(
            {
                "id": str,
                "username": str,
                "access_token": str,
                "refresh_token": str,
                "expires_at": int,
                "client_id": int,
                "client_secret": int,
                "last_data_sync": datetime,
            },
            pk="id",
        )

    if "activities" not in db.table_names():
        db["activities"].create(
            {
                "id": str,
                "type": str,
                "name": str,
                "distance": float,
                "moving_time": int,
                "elapsed_time": int,
                "start_date": str,
                "start_date_local": str,
                "country": str,
                "city": str,
                "state": str,
                "average_speed": float,
                "summary_polyline": str,
                "summary_geojson": str,
                "user_id": str,
            },
            pk="id",
            foreign_keys=[("user_id", "users", "id")],
        )


# see https://developers.strava.com/docs/reference/#api-Activities-getLoggedInAthleteActivities
class Activity(BaseModel):
    id: str
    type: str
    name: str
    distance: float
    moving_time: int
    elapsed_time: int
    start_date: str
    start_date_local: str
    country: str | None = Field(alias="location_country")
    city: str | None = Field(alias="location_city")
    state: str | None = Field(alias="location_state")
    summary_polyline: str = Field(validation_alias=AliasPath("map", "summary_polyline"))
    summary_geojson: Optional[str] = None
    average_speed: float

    @field_validator("id", mode="before")
    def validate_scopes(cls, value):
        return str(value)


# NOTE: In strava, each user gets one client_id. Ideally client_id and
# client_secret would be environment variables but here we don't have any such
# usecase so storing with along with the other data
@dataclass(kw_only=True)
class User:
    id: str = ""
    client_id: str
    client_secret: str
    username: str = ""
    access_token: str = ""
    refresh_token: str = ""
    expires_at: datetime = datetime.utcfromtimestamp(0)
    last_data_sync: datetime = datetime.utcfromtimestamp(0)

    def __post_init__(self):
        if isinstance(self.expires_at, int):
            self.expires_at = datetime.utcfromtimestamp(self.expires_at)
        if isinstance(self.last_data_sync, int):
            self.last_data_sync = datetime.utcfromtimestamp(self.last_data_sync)

    def access_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def initial_access_token(self, db, auth_code):
        resp = requests.post(
            "https://www.strava.com/oauth/token",
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
            },
        )
        access_data = AccessCodeAndMetadata(**resp.json())
        db["users"].upsert(
            {
                **access_data.model_dump(),
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            pk="id",
        )

    def refreshed_access_token(self, db):
        resp = requests.post(
            "https://www.strava.com/oauth/token",
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        access_data = RefreshTokenResponse(**resp.json())
        self.access_token = access_data.access_token
        self.expires_at = datetime.utcfromtimestamp(access_data.expires_at)
        self.refresh_token = access_data.refresh_token
        db["users"].upsert({**access_data.model_dump(), "id": self.id}, pk="id")

    def fetch_activities(self, db):
        all_activities = []
        q = {
            "per_page": "200",
            "before": to_epoch(datetime.utcnow()),
            "after": to_epoch(self.last_data_sync) if self.last_data_sync else None,
        }
        q_string = "&".join([f"{k}={v}" for k, v in q.items() if v])
        page = 1
        while True:
            url = f"https://www.strava.com/api/v3/athlete/activities?{q_string}&page={page}"
            resp = requests.get(
                url, headers={"Authorization": f"Bearer {self.access_token}"}
            )
            page += 1
            activities = resp.json()
            if activities == []:
                break

            # TODO: This operations could probably be vectorized using
            # polars/pandas etc. look into it later
            # But again, a single person would only ever have so many activities
            for a in activities:
                activity = Activity(**a)
                if activity.summary_polyline:
                    activity.summary_geojson = decode_polyline(
                        activity.summary_polyline
                    )
                all_activities.append({**activity.model_dump(), "user_id": self.id})
        db["activities"].upsert_all(all_activities, pk="id")
        db["users"].upsert(
            {"id": self.id, "last_data_sync": int(datetime.utcnow().timestamp())},
            pk="id",
        )


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int


class AccessCodeAndMetadata(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int
    id: str = Field(validation_alias=AliasPath("athlete", "id"))
    username: str = Field(validation_alias=AliasPath("athlete", "username"))

    @field_validator("id", mode="before")
    def validate_scopes(cls, value):
        return str(value)


class AuthCodeAndScope(BaseModel):
    authcode: str = Field(min_length=40, max_length=40)
    scope: set[str]

    @field_validator("scope")
    def validate_scopes(cls, value):
        required_scopes = {"read", "activity:read_all", "profile:read_all", "read_all"}

        if set(value) != required_scopes:
            raise ValueError(f"scope must contain: {required_scopes}")

        return value


def pick_port():
    sock = socket.socket()
    sock.bind(("localhost", 0))
    _, port = sock.getsockname()
    sock.close()
    return port


class TempAuthCodeServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, event, q):
        super().__init__(server_address, RequestHandlerClass)
        self.exit = event
        self.q = q


class TempAuthCodeReqHandler(BaseHTTPRequestHandler):
    server: "TempAuthCodeServer"

    # don't want any logs
    def log_message(self, format, *args):
        return

    def do_GET(self):
        try:
            query_params = parse_qs(urlparse(self.path).query)
            authcode, scope = query_params["code"][0], set(
                query_params["scope"][0].split(",")
            )
            resp = AuthCodeAndScope(authcode=authcode, scope=scope)
            self.server.q.put(resp.authcode)
            click.secho("All good!", fg="green")
            self.send_response(200)
        except ValueError as e:
            click.secho(f"API returning incorrect values/missing scope: {e}", fg="red")
            self.send_response(403)
        except KeyError as e:
            click.secho(f"Missing: {e}", fg="red")
            self.send_response(403)
        except Exception as e:
            click.secho(e, fg="red")
            self.send_response(500)
        finally:
            self.end_headers()
            self.server.exit.set()
