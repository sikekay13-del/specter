from modules.phone import PhoneModule


def test_international_phone_includes_country_and_metadata_limitations():
    rows = PhoneModule().run("+233241234567")
    by_source = {row["source"]: row for row in rows}

    assert by_source["Phone: Number validity"]["state"] == "FOUND"
    assert by_source["Phone: Country"]["detail"] == "Ghana"
    assert "MTN" in by_source["Phone: Carrier metadata"]["detail"]
    assert "originally assigned" in by_source["Phone: Carrier metadata"]["detail"]
    assert by_source["Phone: Subscriber name"]["state"] == "COULD NOT CHECK"
    assert by_source["Phone: Street address"]["state"] == "COULD NOT CHECK"


def test_international_number_works_without_default_country():
    rows = PhoneModule().run("+442071838750")
    by_source = {row["source"]: row for row in rows}

    assert by_source["Phone: Country"]["detail"] == "United Kingdom"
    assert by_source["Phone: International format"]["detail"] == "+442071838750"


def test_national_number_without_region_is_not_misinterpreted():
    rows = PhoneModule(region=None).run("02071838750")

    assert len(rows) == 1
    assert rows[0]["state"] == "COULD NOT CHECK"
    assert "default region" in rows[0]["detail"]


def test_national_number_parses_with_explicit_region():
    rows = PhoneModule(region="GB").run("02071838750")
    by_source = {row["source"]: row for row in rows}

    assert by_source["Phone: Country"]["detail"] == "United Kingdom"
    assert by_source["Phone: International format"]["detail"] == "+442071838750"
