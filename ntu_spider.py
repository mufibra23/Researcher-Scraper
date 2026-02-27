"""
DR-NTU Person Scraper using Scrapy
===================================
Scrapes all NTU researcher/professor profiles from DR-NTU's DSpace 7 REST API.
Extracts: name, title, email, job title, school, research interests, profile URL.

Usage:
    scrapy runspider ntu_spider.py -o ntu_researchers.csv
    scrapy runspider ntu_spider.py -o ntu_researchers.json

Author: Built for Ibra's NTU research
"""

import scrapy
import json


class NTUPersonSpider(scrapy.Spider):
    name = "ntu_persons"

    # === CONFIGURATION ===
    BASE_API = "https://dr.ntu.edu.sg/server/api/discover/search/objects"
    PAGE_SIZE = 20          # Results per page (max 100, 20 is safe)
    MAX_PAGES = None        # Set to e.g. 5 for testing, None for all

    def __init__(self, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if max_pages is not None:
            self.MAX_PAGES = int(max_pages)

    # Polite crawling settings
    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,          # 1 second between requests (be polite!)
        "CONCURRENT_REQUESTS": 1,       # One request at a time
        "ROBOTSTXT_OBEY": False,        # API endpoint, not regular pages
        "LOG_LEVEL": "INFO",
        "FEEDS": {},                    # Controlled via -o flag
        "USER_AGENT": "Mozilla/5.0 (Research Spider - Academic Use)",
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
        },
    }

    def start_requests(self):
        """Start with page 0 of the person search API."""
        url = f"{self.BASE_API}?query=&configuration=person&page=0&size={self.PAGE_SIZE}"
        yield scrapy.Request(url, callback=self.parse, meta={"page": 0})

    def parse(self, response):
        """Parse a page of search results and follow pagination."""
        data = json.loads(response.text)
        search_result = data.get("_embedded", {}).get("searchResult", {})
        objects = search_result.get("_embedded", {}).get("objects", [])

        # --- Extract person data from each result ---
        for obj in objects:
            person = obj.get("_embedded", {}).get("indexableObject", {})
            metadata = person.get("metadata", {})

            # Helper to safely get first value of a metadata field
            def get_meta(key):
                vals = metadata.get(key, [])
                if vals and isinstance(vals, list):
                    return vals[0].get("value", "").strip()
                return ""

            # Build profile URL
            custom_url = get_meta("cris.customurl")
            uuid = person.get("uuid", "")
            if custom_url:
                profile_url = f"https://dr.ntu.edu.sg/entities/person/{custom_url}"
            elif uuid:
                profile_url = f"https://dr.ntu.edu.sg/entities/person/{uuid}"
            else:
                profile_url = ""

            yield {
                "name": get_meta("crisrp.name") or person.get("name", ""),
                "title": get_meta("ntu.person.title"),
                "email": get_meta("person.email"),
                "job_title": get_meta("person.jobTitle"),
                "affiliation": get_meta("oairecerif.person.affiliation"),
                "school": get_meta("ntu.person.supOrgName"),
                "academic_appointment": get_meta("ntu.person.academicAppointments"),
                "research_keywords": get_meta("dc.subject"),
                "orcid": get_meta("oairecerif.identifier.url"),
                "profile_url": profile_url,
                "uuid": uuid,
            }

        # --- Pagination ---
        current_page = response.meta["page"]
        next_link = search_result.get("_links", {}).get("next", {}).get("href")

        if next_link:
            next_page = current_page + 1
            if self.MAX_PAGES and next_page >= self.MAX_PAGES:
                self.logger.info(f"Reached MAX_PAGES limit ({self.MAX_PAGES}). Stopping.")
                return

            self.logger.info(f"Page {current_page} done. Moving to page {next_page}...")
            yield scrapy.Request(next_link, callback=self.parse, meta={"page": next_page})
        else:
            self.logger.info(f"All pages scraped! Last page: {current_page}")
