"""Country identifiers are ISO3, unique per period, and consistent with the metadata."""


def test_iso3_format(annual, quarterly):
    for df in (annual, quarterly):
        assert df.iso3.str.fullmatch(r"[A-Z]{3}").all()


def test_samples_match_metadata(annual, quarterly, meta):
    assert set(annual.iso3) == set(meta[meta.in_annual_sample].iso3)
    assert set(quarterly.iso3) == set(meta[meta.in_quarterly_sample].iso3)
    assert set(quarterly.iso3) <= set(annual.iso3)


def test_every_exclusion_has_reason(meta):
    excl = meta[~meta.in_annual_sample]
    assert excl.exclusion_reason.fillna("").str.len().gt(0).all()


def test_group_labels(meta):
    assert set(meta.country_group) == {"AE", "EMDE"}
    # the 43-member IMF AE list contains these and not these
    g = meta.set_index("iso3").country_group
    assert g["USA"] == "AE" and g["BGR"] == "AE" and g["BRA"] == "EMDE" and g["CHN"] == "EMDE"
