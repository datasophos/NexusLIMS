"""
Mock NEMO API response data for unit testing.

This module provides pytest fixtures with realistic NEMO API responses
based on the actual API schema from https://nemo-demo.atlantislabs.io.

The mock data matches the structure returned by real NEMO endpoints
and includes test data that aligns with existing test expectations.
"""

import copy
from datetime import datetime as dt

import pytest


@pytest.fixture
def mock_users_data():
    """
    Mock NEMO users API response data.

    Based on actual /api/users/ endpoint structure.
    Returns list of user dictionaries matching NEMO API schema.
    """
    return [
        {
            "id": 1,
            "username": "captain",
            "first_name": "Captain",
            "last_name": "Nemo",
            "email": "captain.nemo@nautilus.com",
            "domain": "",
            "notes": None,
            "badge_number": "1",
            "access_expiration": None,
            "is_active": True,
            "is_staff": True,
            "is_user_office": False,
            "is_accounting_officer": False,
            "is_service_personnel": False,
            "is_technician": False,
            "is_facility_manager": True,
            "is_superuser": True,
            "training_required": False,
            "date_joined": "2012-12-10T11:43:37-05:00",
            "last_login": "2025-11-19T17:21:20.687276-05:00",
            "type": 3,
            "onboarding_phases": [1, 2],
            "safety_trainings": [1, 2, 3],
            "physical_access_levels": [],
            "groups": [],
            "user_permissions": [],
            "qualifications": [3, 2, 1],
            "projects": [1, 2, 3],
            "managed_projects": [],
            "gender_name": None,
            "race_name": None,
            "ethnicity_name": None,
            "education_level_name": None,
        },
        {
            "id": 2,
            "username": "professor",
            "first_name": "Pierre",
            "last_name": "Aronnax",
            "email": "pierre.aronnax@nautilus.com",
            "domain": "",
            "notes": "",
            "badge_number": "2",
            "access_expiration": None,
            "is_active": True,
            "is_staff": True,
            "is_user_office": False,
            "is_accounting_officer": False,
            "is_service_personnel": False,
            "is_technician": False,
            "is_facility_manager": False,
            "is_superuser": False,
            "training_required": False,
            "date_joined": "2012-12-10T11:48:43-05:00",
            "last_login": None,
            "type": 2,
            "onboarding_phases": [1],
            "safety_trainings": [2],
            "physical_access_levels": [],
            "groups": [],
            "user_permissions": [],
            "qualifications": [3, 2, 1],
            "projects": [1, 2, 3],
            "managed_projects": [],
            "gender_name": None,
            "race_name": None,
            "ethnicity_name": None,
            "education_level_name": None,
        },
        {
            "id": 3,
            "username": "ned",
            "first_name": "Ned",
            "last_name": "Land",
            "email": "ned.land@nautilus.com",
            "domain": "",
            "notes": None,
            "badge_number": "3",
            "access_expiration": None,
            "is_active": True,
            "is_staff": False,
            "is_user_office": False,
            "is_accounting_officer": False,
            "is_service_personnel": False,
            "is_technician": False,
            "is_facility_manager": False,
            "is_superuser": False,
            "training_required": False,
            "date_joined": "2012-12-10T11:49:38-05:00",
            "last_login": None,
            "type": 1,
            "onboarding_phases": [1],
            "safety_trainings": [1],
            "physical_access_levels": [],
            "groups": [],
            "user_permissions": [],
            "qualifications": [
                129,
                44,
                123,
                40,
                53,
                36,
                31,
                3,
                13,
                19,
                59,
                95,
                61,
                2,
                1,
                33,
                10,
            ],
            "projects": [1, 2, 3],
            "managed_projects": [],
            "gender_name": None,
            "race_name": None,
            "ethnicity_name": None,
            "education_level_name": None,
        },
        {
            "id": 4,
            "username": "commander",
            "first_name": "Commander",
            "last_name": "Farragut",
            "email": "commander.farragut@nautilus.com",
            "domain": "",
            "notes": None,
            "badge_number": "4",
            "access_expiration": None,
            "is_active": True,
            "is_staff": False,
            "is_user_office": False,
            "is_accounting_officer": True,
            "is_service_personnel": False,
            "is_technician": False,
            "is_facility_manager": False,
            "is_superuser": False,
            "training_required": False,
            "date_joined": "2012-12-10T11:48:43-05:00",
            "last_login": None,
            "type": 2,
            "onboarding_phases": [1],
            "safety_trainings": [1],
            "physical_access_levels": [],
            "groups": [],
            "user_permissions": [],
            "qualifications": [3, 2, 1],
            "projects": [1, 2, 3],
            "managed_projects": [],
            "gender_name": None,
            "race_name": None,
            "ethnicity_name": None,
            "education_level_name": None,
        },
    ]


@pytest.fixture
def mock_tools_data():
    """
    Mock NEMO tools API response data.

    Based on actual /api/tools/ endpoint structure.
    Returns list of tool dictionaries matching NEMO API schema.
    """
    return [
        {
            "id": 1,
            "name": "643 Titan (S)TEM (probe corrected)",
            "visible": True,
            "_description": "",
            "_serial": "",
            "_image": None,
            "_tool_calendar_color": "#33ad33",
            "_category": "Microscopy",
            "_operational": True,
            "_properties": None,
            "_location": "643/B100",
            "_phone_number": "x1234",
            "_notification_email_address": "service@nautilus.com",
            "_qualifications_never_expire": False,
            "_ask_to_leave_area_when_done_using": False,
            "_grant_badge_reader_access_upon_qualification": None,
            "_reservation_horizon": 14,
            "_minimum_usage_block_time": None,
            "_maximum_usage_block_time": None,
            "_maximum_reservations_per_day": None,
            "_maximum_future_reservations": None,
            "_minimum_time_between_reservations": None,
            "_maximum_future_reservation_time": None,
            "_missed_reservation_threshold": 30,
            "_max_delayed_logoff": None,
            "_pre_usage_questions": None,
            "_post_usage_questions": "",
            "_policy_off_between_times": False,
            "_policy_off_start_time": None,
            "_policy_off_end_time": None,
            "_policy_off_weekend": False,
            "_operation_mode": 0,
            "parent_tool": None,
            "_primary_owner": 1,
            "_interlock": None,
            "_requires_area_access": None,
            "_grant_physical_access_level_upon_qualification": 2,
            "_backup_owners": [3, 2],
            "_superusers": [],
            "_staff": [],
            "_adjustment_request_reviewers": [],
        },
        {
            "id": 3,
            "name": "642 FEI Titan",
            "visible": True,
            "_description": "",
            "_serial": "",
            "_image": None,
            "_tool_calendar_color": "#33ad33",
            "_category": "Microscopy",
            "_operational": True,
            "_properties": None,
            "_location": "642/A100",
            "_phone_number": "x5678",
            "_notification_email_address": "service@nautilus.com",
            "_qualifications_never_expire": False,
            "_ask_to_leave_area_when_done_using": False,
            "_grant_badge_reader_access_upon_qualification": None,
            "_reservation_horizon": 14,
            "_minimum_usage_block_time": None,
            "_maximum_usage_block_time": None,
            "_maximum_reservations_per_day": None,
            "_maximum_future_reservations": None,
            "_minimum_time_between_reservations": None,
            "_maximum_future_reservation_time": None,
            "_missed_reservation_threshold": 30,
            "_max_delayed_logoff": None,
            "_pre_usage_questions": None,
            "_post_usage_questions": "",
            "_policy_off_between_times": False,
            "_policy_off_start_time": None,
            "_policy_off_end_time": None,
            "_policy_off_weekend": False,
            "_operation_mode": 0,
            "parent_tool": None,
            "_primary_owner": 1,
            "_interlock": None,
            "_requires_area_access": None,
            "_grant_physical_access_level_upon_qualification": 2,
            "_backup_owners": [3, 2],
            "_superusers": [],
            "_staff": [],
            "_adjustment_request_reviewers": [],
        },
        {
            "id": 10,
            "name": "Test Tool",
            "visible": True,
            "_description": "Tool for testing",
            "_serial": "",
            "_image": None,
            "_tool_calendar_color": "#ff5733",
            "_category": "Testing",
            "_operational": True,
            "_properties": None,
            "_location": "100/Test",
            "_phone_number": "x9999",
            "_notification_email_address": "test@nautilus.com",
            "_qualifications_never_expire": False,
            "_ask_to_leave_area_when_done_using": False,
            "_grant_badge_reader_access_upon_qualification": None,
            "_reservation_horizon": 14,
            "_minimum_usage_block_time": None,
            "_maximum_usage_block_time": None,
            "_maximum_reservations_per_day": None,
            "_maximum_future_reservations": None,
            "_minimum_time_between_reservations": None,
            "_maximum_future_reservation_time": None,
            "_missed_reservation_threshold": 30,
            "_max_delayed_logoff": None,
            "_pre_usage_questions": None,
            "_post_usage_questions": "",
            "_policy_off_between_times": False,
            "_policy_off_start_time": None,
            "_policy_off_end_time": None,
            "_policy_off_weekend": False,
            "_operation_mode": 0,
            "parent_tool": None,
            "_primary_owner": 1,
            "_interlock": None,
            "_requires_area_access": None,
            "_grant_physical_access_level_upon_qualification": 2,
            "_backup_owners": [2],
            "_superusers": [],
            "_staff": [],
            "_adjustment_request_reviewers": [],
        },
        {
            "id": 15,
            "name": "642 JEOL 3010",
            "visible": True,
            "_description": "",
            "_serial": "",
            "_image": None,
            "_tool_calendar_color": "#33ad33",
            "_category": "Microscopy",
            "_operational": True,
            "_properties": None,
            "_location": "642/C100",
            "_phone_number": "x2222",
            "_notification_email_address": "service@nautilus.com",
            "_qualifications_never_expire": False,
            "_ask_to_leave_area_when_done_using": False,
            "_grant_badge_reader_access_upon_qualification": None,
            "_reservation_horizon": 14,
            "_minimum_usage_block_time": None,
            "_maximum_usage_block_time": None,
            "_maximum_reservations_per_day": None,
            "_maximum_future_reservations": None,
            "_minimum_time_between_reservations": None,
            "_maximum_future_reservation_time": None,
            "_missed_reservation_threshold": 30,
            "_max_delayed_logoff": None,
            "_pre_usage_questions": None,
            "_post_usage_questions": "",
            "_policy_off_between_times": False,
            "_policy_off_start_time": None,
            "_policy_off_end_time": None,
            "_policy_off_weekend": False,
            "_operation_mode": 0,
            "parent_tool": None,
            "_primary_owner": 1,
            "_interlock": None,
            "_requires_area_access": None,
            "_grant_physical_access_level_upon_qualification": 2,
            "_backup_owners": [3, 2],
            "_superusers": [],
            "_staff": [],
            "_adjustment_request_reviewers": [],
        },
    ]


@pytest.fixture
def mock_projects_data():
    """
    Mock NEMO projects API response data.

    Based on actual /api/projects/ endpoint structure.
    Returns list of project dictionaries matching NEMO API schema.
    """
    return [
        {
            "id": 13,
            "principal_investigators": [],
            "users": [1, 2, 3, 4],
            "name": "Gaithersburg",
            "application_identifier": "PROJ.2019.13",
            "start_date": None,
            "active": True,
            "allow_consumable_withdrawals": True,
            "allow_staff_charges": True,
            "account": 1,
            "discipline": None,
            "project_types": [1],
            "only_allow_tools": [],
            "project_name": None,
            "contact_name": None,
            "contact_phone": None,
            "contact_email": None,
            "expires_on": None,
            "addressee": None,
            "comments": None,
            "no_charge": None,
            "no_tax": None,
            "no_cap": None,
            "category": None,
            "institution": None,
            "department": None,
            "staff_host": None,
        },
        {
            "id": 14,
            "principal_investigators": [],
            "users": [1, 2],
            "name": "Boulder",
            "application_identifier": "PROJ.2019.14",
            "start_date": None,
            "active": True,
            "allow_consumable_withdrawals": True,
            "allow_staff_charges": True,
            "account": 2,
            "discipline": 1,
            "project_types": [],
            "only_allow_tools": [],
            "project_name": None,
            "contact_name": None,
            "contact_phone": None,
            "contact_email": None,
            "expires_on": None,
            "addressee": None,
            "comments": None,
            "no_charge": None,
            "no_tax": None,
            "no_cap": None,
            "category": None,
            "institution": None,
            "department": None,
            "staff_host": None,
        },
        {
            "id": 15,
            "principal_investigators": [],
            "users": [3, 4],
            "name": "ODI",
            "application_identifier": "PROJ.2019.15",
            "start_date": None,
            "active": True,
            "allow_consumable_withdrawals": True,
            "allow_staff_charges": True,
            "account": 3,
            "discipline": None,
            "project_types": [],
            "only_allow_tools": [],
            "project_name": None,
            "contact_name": None,
            "contact_phone": None,
            "contact_email": None,
            "expires_on": None,
            "addressee": None,
            "comments": None,
            "no_charge": None,
            "no_tax": None,
            "no_cap": None,
            "category": None,
            "institution": None,
            "department": None,
            "staff_host": None,
        },
        {
            "id": 16,
            "principal_investigators": [],
            "users": [1],
            "name": "Test",
            "application_identifier": "PROJ.TEST.16",
            "start_date": None,
            "active": True,
            "allow_consumable_withdrawals": True,
            "allow_staff_charges": True,
            "account": 4,
            "discipline": None,
            "project_types": [],
            "only_allow_tools": [],
            "project_name": None,
            "contact_name": None,
            "contact_phone": None,
            "contact_email": None,
            "expires_on": None,
            "addressee": None,
            "comments": None,
            "no_charge": None,
            "no_tax": None,
            "no_cap": None,
            "category": None,
            "institution": None,
            "department": None,
            "staff_host": None,
        },
    ]


@pytest.fixture
def mock_reservations_data():
    """
    Mock NEMO reservations API response data.

    Based on actual /api/reservations/ endpoint structure.
    Includes various test scenarios with question_data for testing.
    """
    return [
        {
            "id": 187,
            "question_data": {
                "project_id": {"user_input": "NexusLIMS-Test"},
                "experiment_title": {"user_input": "Test Reservation Title"},
                "experiment_purpose": {
                    "user_input": "Testing the NEMO harvester integration.",
                },
                "data_consent": {"user_input": "Agree"},
                "sample_group": {
                    "user_input": {
                        "0": {
                            "sample_name": "test_sample_1",
                            "sample_or_pid": "Sample Name",
                            "sample_details": "A test sample for harvester testing",
                        },
                    },
                },
            },
            "configuration_options": [],
            "creation_time": "2021-08-02T10:00:00-06:00",
            "start": "2021-08-02T11:00:00-06:00",
            "end": "2021-08-02T16:00:00-06:00",
            "short_notice": False,
            "cancelled": False,
            "cancellation_time": None,
            "missed": False,
            "shortened": False,
            "additional_information": None,
            "self_configuration": False,
            "title": "",
            "validated": False,
            "waived": False,
            "waived_on": None,
            "user": 3,  # ned
            "creator": 3,
            "tool": 10,
            "area": None,
            "project": 13,
            "cancelled_by": None,
            "descendant": None,
            "validated_by": None,
            "waived_by": None,
        },
        {
            "id": 188,
            "question_data": {},
            "configuration_options": [],
            "creation_time": "2021-08-03T09:00:00-06:00",
            "start": "2021-08-03T10:00:00-06:00",
            "end": "2021-08-03T17:00:00-06:00",
            "short_notice": False,
            "cancelled": False,
            "cancellation_time": None,
            "missed": False,
            "shortened": False,
            "additional_information": None,
            "self_configuration": False,
            "title": "",
            "validated": False,
            "waived": False,
            "waived_on": None,
            "user": 2,
            "creator": 2,
            "tool": 10,
            "area": None,
            "project": 13,
            "cancelled_by": None,
            "descendant": None,
            "validated_by": None,
            "waived_by": None,
        },
        {
            "id": 189,
            "question_data": {
                "project_id": {"user_input": "DisagreeConsent"},
                "experiment_title": {"user_input": "User disagrees with consent"},
                "data_consent": {"user_input": "Disagree"},
            },
            "configuration_options": [],
            "creation_time": "2021-08-04T09:00:00-06:00",
            "start": "2021-08-04T10:00:00-06:00",
            "end": "2021-08-04T17:00:00-06:00",
            "short_notice": False,
            "cancelled": False,
            "cancellation_time": None,
            "missed": False,
            "shortened": False,
            "additional_information": None,
            "self_configuration": False,
            "title": "",
            "validated": False,
            "waived": False,
            "waived_on": None,
            "user": 2,
            "creator": 2,
            "tool": 10,
            "area": None,
            "project": 13,
            "cancelled_by": None,
            "descendant": None,
            "validated_by": None,
            "waived_by": None,
        },
        # Reservation with elements in periodic table - multiple samples
        {
            "id": 200,
            "question_data": {
                "project_id": {"user_input": "ElementsTest"},
                "experiment_title": {
                    "user_input": (
                        "Test reservation for multiple samples, "
                        "some with elements, some not"
                    ),
                },
                "experiment_purpose": {"user_input": "testing"},
                "data_consent": {"user_input": "Agree"},
                "sample_group": {
                    "user_input": {
                        "0": {
                            "sample_name": "sample 1.1",
                            "sample_or_pid": "Sample Name",
                            "sample_details": "no elements",
                        },
                        "1": {
                            "sample_name": "sample 1.2",
                            "sample_or_pid": "Sample Name",
                            "sample_details": "some elements",
                            "periodic_table": ["S", "Rb", "Sb", "Re", "Cm"],
                        },
                        "2": {
                            "sample_name": "sample 1.3",
                            "sample_or_pid": "Sample Name",
                            "sample_details": "one element",
                            "periodic_table": ["Ir"],
                        },
                    },
                },
            },
            "configuration_options": [],
            "creation_time": "2023-02-13T12:00:00-07:00",
            "start": "2023-02-13T13:00:00-07:00",
            "end": "2023-02-13T14:00:00-07:00",
            "short_notice": False,
            "cancelled": False,
            "cancellation_time": None,
            "missed": False,
            "shortened": False,
            "additional_information": None,
            "self_configuration": False,
            "title": "",
            "validated": False,
            "waived": False,
            "waived_on": None,
            "user": 3,
            "creator": 3,
            "tool": 10,
            "area": None,
            "project": 13,
            "cancelled_by": None,
            "descendant": None,
            "validated_by": None,
            "waived_by": None,
        },
        # Test reservation - no elements (PID sample)
        {
            "id": 201,
            "question_data": {
                "project_id": {"user_input": "TestNoElements"},
                "experiment_title": {"user_input": "Test reservation with no elements"},
                "experiment_purpose": {"user_input": "testing no elements"},
                "data_consent": {"user_input": "Agree"},
                "sample_group": {
                    "user_input": {
                        "0": {
                            "sample_name": "sample 1",
                            "sample_or_pid": "PID",
                            "sample_details": None,
                        },
                    },
                },
            },
            "configuration_options": [],
            "creation_time": "2023-02-13T09:00:00-07:00",
            "start": "2023-02-13T10:00:00-07:00",
            "end": "2023-02-13T11:00:00-07:00",
            "short_notice": False,
            "cancelled": False,
            "cancellation_time": None,
            "missed": False,
            "shortened": False,
            "additional_information": None,
            "self_configuration": False,
            "title": "",
            "validated": False,
            "waived": False,
            "waived_on": None,
            "user": 3,
            "creator": 3,
            "tool": 10,
            "area": None,
            "project": 13,
            "cancelled_by": None,
            "descendant": None,
            "validated_by": None,
            "waived_by": None,
        },
        # Test reservation - some elements
        {
            "id": 202,
            "question_data": {
                "project_id": {"user_input": "TestSomeElements"},
                "experiment_title": {
                    "user_input": "Test reservation with some elements",
                },
                "experiment_purpose": {"user_input": "testing some elements"},
                "data_consent": {"user_input": "Agree"},
                "sample_group": {
                    "user_input": {
                        "0": {
                            "sample_name": "sample 2",
                            "sample_or_pid": "PID",
                            "sample_details": None,
                            "periodic_table": ["H", "Ti", "Cu", "Sb", "Re"],
                        },
                    },
                },
            },
            "configuration_options": [],
            "creation_time": "2023-02-13T10:00:00-07:00",
            "start": "2023-02-13T11:00:00-07:00",
            "end": "2023-02-13T12:00:00-07:00",
            "short_notice": False,
            "cancelled": False,
            "cancellation_time": None,
            "missed": False,
            "shortened": False,
            "additional_information": None,
            "self_configuration": False,
            "title": "",
            "validated": False,
            "waived": False,
            "waived_on": None,
            "user": 3,
            "creator": 3,
            "tool": 10,
            "area": None,
            "project": 13,
            "cancelled_by": None,
            "descendant": None,
            "validated_by": None,
            "waived_by": None,
        },
        # Test reservation - all elements
        {
            "id": 203,
            "question_data": {
                "project_id": {"user_input": "TestAllElements"},
                "experiment_title": {
                    "user_input": "Test reservation with all elements",
                },
                "experiment_purpose": {"user_input": "testing all elements"},
                "data_consent": {"user_input": "Agree"},
                "sample_group": {
                    "user_input": {
                        "0": {
                            "sample_name": "sample 3",
                            "sample_or_pid": "Sample Name",
                            "sample_details": "testing",
                            "periodic_table": [
                                "H",
                                "He",
                                "Li",
                                "Be",
                                "B",
                                "C",
                                "N",
                                "O",
                                "F",
                                "Ne",
                                "Na",
                                "Mg",
                                "Al",
                                "Si",
                                "P",
                                "S",
                                "Cl",
                                "Ar",
                                "K",
                                "Ca",
                                "Sc",
                                "Ti",
                                "V",
                                "Cr",
                                "Mn",
                                "Fe",
                                "Co",
                                "Ni",
                                "Cu",
                                "Zn",
                                "Ga",
                                "Ge",
                                "As",
                                "Se",
                                "Br",
                                "Kr",
                                "Rb",
                                "Sr",
                                "Y",
                                "Zr",
                                "Nb",
                                "Mo",
                                "Tc",
                                "Ru",
                                "Rh",
                                "Pd",
                                "Ag",
                                "Cd",
                                "In",
                                "Sn",
                                "Sb",
                                "Te",
                                "I",
                                "Xe",
                                "Cs",
                                "Ba",
                                "La",
                                "Ce",
                                "Pr",
                                "Nd",
                                "Pm",
                                "Sm",
                                "Eu",
                                "Gd",
                                "Tb",
                                "Dy",
                                "Ho",
                                "Er",
                                "Tm",
                                "Yb",
                                "Lu",
                                "Hf",
                                "Ta",
                                "W",
                                "Re",
                                "Os",
                                "Ir",
                                "Pt",
                                "Au",
                                "Hg",
                                "Tl",
                                "Pb",
                                "Bi",
                                "Po",
                                "At",
                                "Rn",
                                "Fr",
                                "Ra",
                                "Ac",
                                "Th",
                                "Pa",
                                "U",
                                "Np",
                                "Pu",
                                "Am",
                                "Cm",
                                "Bk",
                                "Cf",
                                "Es",
                                "Fm",
                                "Md",
                                "No",
                                "Lr",
                                "Rf",
                                "Db",
                                "Sg",
                                "Bh",
                                "Hs",
                                "Mt",
                                "Ds",
                                "Rg",
                                "Cn",
                                "Nh",
                                "Fl",
                                "Mc",
                                "Lv",
                                "Ts",
                                "Og",
                            ],
                        },
                    },
                },
            },
            "configuration_options": [],
            "creation_time": "2023-02-13T11:00:00-07:00",
            "start": "2023-02-13T12:00:00-07:00",
            "end": "2023-02-13T13:00:00-07:00",
            "short_notice": False,
            "cancelled": False,
            "cancellation_time": None,
            "missed": False,
            "shortened": False,
            "additional_information": None,
            "self_configuration": False,
            "title": "",
            "validated": False,
            "waived": False,
            "waived_on": None,
            "user": 3,
            "creator": 3,
            "tool": 10,
            "area": None,
            "project": 13,
            "cancelled_by": None,
            "descendant": None,
            "validated_by": None,
            "waived_by": None,
        },
    ]


@pytest.fixture
def mock_usage_events_data():
    """
    Mock NEMO usage_events API response data.

    Based on actual /api/usage_events/ endpoint structure.
    Includes various test scenarios for testing.
    """
    return [
        {
            "id": 29,
            "start": "2021-09-01T15:00:00-06:00",
            "end": "2021-09-01T18:00:00-06:00",
            "has_ended": 25,
            "validated": False,
            "remote_work": False,
            "training": False,
            "pre_run_data": "",
            "run_data": "",
            "waived": False,
            "waived_on": None,
            "user": 3,  # ned
            "operator": 3,
            "project": 13,
            "tool": 10,
            "validated_by": None,
            "waived_by": None,
        },
        {
            "id": 30,
            "start": "2021-09-05T13:57:00.000000-06:00",
            "end": "2021-09-05T17:00:00.000000-06:00",
            "has_ended": 27,
            "validated": False,
            "remote_work": False,
            "training": False,
            "pre_run_data": "",
            "run_data": "",
            "waived": False,
            "waived_on": None,
            "user": 3,
            "operator": 3,
            "project": 13,
            "tool": 10,
            "validated_by": None,
            "waived_by": None,
        },
        {
            "id": 31,
            "start": "2021-09-10T10:00:00-06:00",
            "end": None,  # Not yet ended
            "has_ended": 0,
            "validated": False,
            "remote_work": False,
            "training": False,
            "pre_run_data": "",
            "run_data": None,
            "waived": False,
            "waived_on": None,
            "user": 2,
            "operator": 2,
            "project": 14,
            "tool": 3,
            "validated_by": None,
            "waived_by": None,
        },
    ]


def filter_by_params(data, params):  # noqa: PLR0912
    """
    Filter mock API data based on query parameters.

    Helper function to simulate NEMO API filtering logic.

    Parameters
    ----------
    data : list
        List of dictionaries representing API objects
    params : dict
        Query parameters for filtering

    Returns
    -------
    filtered : list
        Filtered list matching the parameters (deep copied to avoid mutation)
    """
    # Make a deep copy to avoid mutation issues when connector modifies returned objects
    filtered = copy.deepcopy(data)

    # Filter by ID
    if "id" in params:
        filtered = [item for item in filtered if item["id"] == params["id"]]
    if "id__in" in params:
        ids = [int(i) for i in params["id__in"].split(",")]
        filtered = [item for item in filtered if item["id"] in ids]

    # Filter by username (for users)
    if "username__iexact" in params:
        filtered = [
            item
            for item in filtered
            if item.get("username", "").lower() == params["username__iexact"].lower()
        ]
    if "username__in" in params:
        usernames = [u.lower() for u in params["username__in"].split(",")]
        filtered = [
            item for item in filtered if item.get("username", "").lower() in usernames
        ]

    # Filter by tool_id (for reservations/usage_events)
    if "tool_id" in params:
        tool_id = (
            int(params["tool_id"])
            if isinstance(params["tool_id"], str)
            else params["tool_id"]
        )
        filtered = [item for item in filtered if item.get("tool") == tool_id]
    if "tool_id__in" in params:
        tool_ids = [int(i) for i in params["tool_id__in"].split(",")]
        filtered = [item for item in filtered if item.get("tool") in tool_ids]

    # Filter by user_id (for usage_events)
    if "user_id" in params:
        user_id = (
            int(params["user_id"])
            if isinstance(params["user_id"], str)
            else params["user_id"]
        )
        filtered = [item for item in filtered if item.get("user") == user_id]

    # Filter by cancelled status (for reservations)
    if "cancelled" in params:
        cancelled_val = params["cancelled"]
        if isinstance(cancelled_val, str):
            cancelled_val = cancelled_val.lower() in ["true", "1", "yes"]
        filtered = [
            item for item in filtered if item.get("cancelled", False) == cancelled_val
        ]

    # Filter by date range (for reservations/usage_events)
    if "start__gte" in params:
        start_gte = params["start__gte"]
        if isinstance(start_gte, str):
            start_gte = dt.fromisoformat(start_gte)
        filtered = [
            item
            for item in filtered
            if item.get("start") and dt.fromisoformat(item["start"]) >= start_gte
        ]

    if "end__lte" in params:
        end_lte = params["end__lte"]
        if isinstance(end_lte, str):
            end_lte = dt.fromisoformat(end_lte)
        filtered = [
            item
            for item in filtered
            if item.get("end") and dt.fromisoformat(item["end"]) <= end_lte
        ]

    return filtered
