import phonenumbers
from phonenumbers import carrier, geocoder, timezone, PhoneNumberType
from .base import BaseScraper

LINE_TYPES = {
    PhoneNumberType.MOBILE: "Mobile",
    PhoneNumberType.FIXED_LINE: "Landline",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "Landline or mobile",
    PhoneNumberType.VOIP: "VoIP",
    PhoneNumberType.TOLL_FREE: "Toll free",
}


class PhoneModule(BaseScraper):
    name = "phone"
    supports = ["phone"]

    def __init__(self, region=None, **kwargs):
        super().__init__(**kwargs)
        self.region = region

    def _row(self, source, state, detail):
        return {
            "source": source,
            "url": "",
            "state": state,
            "found": state == "FOUND",
            "detail": detail,
        }

    def run(self, target):
        try:
            num = phonenumbers.parse(target, self.region)
        except phonenumbers.NumberParseException as e:
            hint = (
                " Use international format with +country code, or provide a "
                "default region for a national number."
            )
            return [self._row("Phone: Parse", "COULD NOT CHECK", f"{e}.{hint}")]

        if not phonenumbers.is_valid_number(num):
            region = f" in region {self.region}" if self.region else ""
            return [self._row(
                "Phone: Number validity",
                "NOT FOUND",
                f"Number is not valid according to numbering-plan metadata{region}.",
            )]

        line = LINE_TYPES.get(phonenumbers.number_type(num), "Unknown")
        region_code = phonenumbers.region_code_for_number(num)
        country = geocoder.country_name_for_number(num, "en")
        country_detail = country or (
            "Non-geographic numbering plan"
            if region_code == "001"
            else ""
        )
        carrier_name = carrier.name_for_number(num, "en")
        location = geocoder.description_for_number(num, "en")
        timezones = timezone.time_zones_for_number(num)

        results = [
            self._row(
                "Phone: Number validity",
                "FOUND",
                "Valid according to libphonenumber numbering-plan metadata.",
            ),
            self._row(
                "Phone: International format",
                "FOUND",
                phonenumbers.format_number(
                    num, phonenumbers.PhoneNumberFormat.E164
                ),
            ),
            self._row(
                "Phone: Country",
                "FOUND" if country_detail else "COULD NOT CHECK",
                country_detail or "Country could not be determined from numbering metadata.",
            ),
            self._row(
                "Phone: Numbering location",
                "FOUND" if location else "NOT FOUND",
                (
                    f"{location}; approximate numbering-plan region, not a street address."
                    if location
                    else "No geographic numbering-plan description available."
                ),
            ),
            self._row(
                "Phone: Carrier metadata",
                "FOUND" if carrier_name else "NOT FOUND",
                (
                    f"{carrier_name}; may be the originally assigned carrier, "
                    "not the current carrier after number portability."
                    if carrier_name
                    else "No carrier metadata available for this number."
                ),
            ),
            self._row(
                "Phone: Line type",
                "FOUND" if line != "Unknown" else "NOT FOUND",
                line if line != "Unknown" else "No line-type metadata available.",
            ),
            self._row(
                "Phone: Timezone",
                "FOUND" if timezones else "NOT FOUND",
                (
                    ", ".join(timezones)
                    if timezones
                    else "No timezone metadata available."
                ),
            ),
            self._row(
                "Phone: Subscriber name",
                "COULD NOT CHECK",
                "No free, public, worldwide subscriber-name directory is used; "
                "no identity lookup was attempted.",
            ),
            self._row(
                "Phone: Street address",
                "COULD NOT CHECK",
                "A phone number does not reveal a subscriber's street address; "
                "no address lookup was attempted.",
            ),
        ]
        return results