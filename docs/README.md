
# Table of Contents

1.  [strava-to-sqlite](#org1ad9cda)
    1.  [Get started](#orge43484f)
        1.  [Install](#org86f687d)
        2.  [Auth and fetch](#orge3f733d)
        3.  [Explore](#org013843f)
    2.  [Roadmap](#orga17cf57)
    3.  [Links, Resources and Thanks](#orga247165)


<a id="org1ad9cda"></a>

# strava-to-sqlite


<a id="orge43484f"></a>

## Get started


<a id="org86f687d"></a>

### Install

    pip install strava-to-sqlite


<a id="orge3f733d"></a>

### Auth and fetch

    # - Allow auth via browser oauth flow
    # - Saves credentials to database
    strava-to-sqlite auth strava_dump.db
    
    # - Fetches and stores strava activities since last sync for all users
    strava-to-sqlite sync strava_dump.db


<a id="org013843f"></a>

### Explore

Strava API sends [polylines](https://developers.google.com/maps/documentation/routes/polylinedecoder) which are transformed to [GeoJSON LineString](https://datatracker.ietf.org/doc/html/rfc7946#section-3.1.4) by `strava-to-sqlite` and can rendered on map with [datasette-leaflet-geojson](https://datasette.io/plugins/datasette-leaflet-geojson) and [datasette](https://datasette.io/).

    # assuming datasette is installed
    datasette install datasette-leaflet-geojson
    datasette strava_dump.db


<a id="orga17cf57"></a>

## Roadmap

-   [ ] Overall clean-up/refactor
-   [ ] Add tests
-   [ ] Client side rate-limiting and retries
-   [ ] Option to fetch for individual user (currently fetches for all authenticated users)


<a id="orga247165"></a>

## Links, Resources and Thanks

-   Strava: [Forum](https://communityhub.strava.com/) | [Strava API](https://developers.strava.com/docs/#client-code) | [Rate Limits](https://developers.strava.com/docs/rate-limits/) | [Auth](https://developers.strava.com/docs/authentication/) | [Swagger UI](https://developers.strava.com/playground/)
-   Similar Projects
    -   [stravalib/stravalib](https://github.com/stravalib/stravalib)
    -   [brendano257/Strava2SQL](https://github.com/brendano257/Strava2SQL)
    -   [ghing/strava-to-sqlite](https://github.com/ghing/strava-to-sqlite)
    -   [yihong0618/running<sub>page</sub>](https://github.com/yihong0618/running_page)
    -   [marcusvolz/strava<sub>py</sub>](https://github.com/marcusvolz/strava_py)

