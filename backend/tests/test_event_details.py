import pytest
from pydantic import ValidationError

from backend.app.models.events import (
    CareNoteDetails,
    ChangingDetails,
    FeedingDetails,
    MedicationDetails,
    RepositioningDetails,
)


def test_valid_feeding_details():
    details = FeedingDetails(
        feeding_type="tube",
        food_or_formula="Formula A",
        quantity=250,
        unit="mL",
        route="g_tube",
        tolerance="mostly_tolerated",
        observations=["mild coughing near end"],
    )

    assert details.feeding_type == "tube"
    assert details.quantity == 250
    assert details.unit == "mL"
    assert details.observations == ["mild coughing near end"]
    assert details.issues == []


def test_feeding_quantity_must_be_positive_when_present():
    with pytest.raises(ValidationError):
        FeedingDetails(
            feeding_type="tube",
            quantity=-250,
            unit="mL",
        )


def test_valid_medication_details():
    details = MedicationDetails(
        medication_name="Medication A",
        dose=10,
        dose_unit="mg",
        route="oral",
    )

    assert details.medication_name == "Medication A"
    assert details.dose == 10
    assert details.dose_unit == "mg"
    assert details.is_prn is False


def test_medication_dose_must_be_positive():
    with pytest.raises(ValidationError):
        MedicationDetails(
            medication_name="Medication A",
            dose=-10,
            dose_unit="mg",
        )


def test_valid_changing_details():
    details = ChangingDetails(
        change_type="diaper",
        condition="wet",
        skin_condition="slight redness",
        barrier_cream_applied=True,
        clothing_changed=False,
    )

    assert details.condition == "wet"
    assert details.barrier_cream_applied is True
    assert details.clothing_changed is False


def test_changing_condition_must_be_supported():
    with pytest.raises(ValidationError):
        ChangingDetails(
            change_type="diaper",
            condition="unknown",
        )


def test_valid_repositioning_details():
    details = RepositioningDetails(
        from_position="back",
        to_position="left_side",
        assistance_level="full",
        reason="scheduled repositioning",
    )

    assert details.from_position == "back"
    assert details.to_position == "left_side"


def test_repositioning_requires_destination_position():
    with pytest.raises(ValidationError):
        RepositioningDetails(
            from_position="back",
        )


def test_valid_care_note_details():
    details = CareNoteDetails(
        category="symptom_observation",
        observation="Mild coughing during feeding",
        severity_optional="mild",
    )

    assert details.category == "symptom_observation"
    assert details.observation == "Mild coughing during feeding"


def test_unknown_detail_fields_are_rejected():
    with pytest.raises(ValidationError):
        FeedingDetails(
            feeding_type="tube",
            quantity=250,
            unit="mL",
            typo_field="should not be accepted",
        )