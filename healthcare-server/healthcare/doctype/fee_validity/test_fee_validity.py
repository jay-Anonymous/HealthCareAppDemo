# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and Contributors
# See license.txt


import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, date_diff, nowdate

from erpnext.accounts.doctype.pos_profile.test_pos_profile import make_pos_profile

from healthcare.healthcare.doctype.patient_appointment.test_patient_appointment import (
	create_appointment,
	create_healthcare_docs,
	create_healthcare_service_items,
	update_status,
)

EXTRA_TEST_RECORD_DEPENDENCIES = ["Company"]


class TestFeeValidity(IntegrationTestCase):
	def setUp(self):
		frappe.db.sql("""delete from `tabPatient Appointment`""")
		frappe.db.sql("""delete from `tabFee Validity`""")
		frappe.db.sql("""delete from `tabPatient`""")
		make_pos_profile()

	def test_fee_validity(self):
		item = create_healthcare_service_items()
		healthcare_settings = frappe.get_single("Healthcare Settings")
		healthcare_settings.enable_free_follow_ups = 1
		healthcare_settings.max_visits = 1
		healthcare_settings.valid_days = 7
		healthcare_settings.show_payment_popup = 1
		healthcare_settings.op_consulting_charge_item = item
		healthcare_settings.save(ignore_permissions=True)
		patient, practitioner = create_healthcare_docs()

		# For first appointment, invoice is generated. First appointment not considered in fee validity
		appointment = create_appointment(patient, practitioner, nowdate())
		fee_validity = frappe.db.exists(
			"Fee Validity",
			{"patient": patient, "practitioner": practitioner, "patient_appointment": appointment.name},
		)
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)
		self.assertTrue(fee_validity)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Active")

		# appointment should not be invoiced as it is within fee validity
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 4))
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 0)

		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "visited"), 1)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Completed")

		# appointment should be invoiced as it is within fee validity but the max_visits are exceeded, should insert new fee validity
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 5), invoice=1)
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)

		fee_validity = frappe.db.exists(
			"Fee Validity",
			{"patient": patient, "practitioner": practitioner, "patient_appointment": appointment.name},
		)
		self.assertTrue(fee_validity)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Active")

		# appointment should be invoiced as it is not within fee validity and insert new fee validity
		appointment = create_appointment(patient, practitioner, add_days(nowdate(), 13), invoice=1)
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)

		fee_validity = frappe.db.exists(
			"Fee Validity",
			{"patient": patient, "practitioner": practitioner, "patient_appointment": appointment.name},
		)
		self.assertTrue(fee_validity)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Active")

		# For first appointment cancel should cancel fee validity
		update_status(appointment.name, "Cancelled")
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Cancelled")

	def test_practitioner_fee_validity(self):
		self.setUp()
		item = create_healthcare_service_items()
		healthcare_settings = frappe.get_single("Healthcare Settings")
		healthcare_settings.enable_free_follow_ups = 1
		healthcare_settings.max_visits = 1
		healthcare_settings.valid_days = 7
		healthcare_settings.show_payment_popup = 1
		healthcare_settings.op_consulting_charge_item = item
		healthcare_settings.save(ignore_permissions=True)
		patient, practitioner = create_healthcare_docs()
		frappe.db.set_value(
			"Healthcare Practitioner",
			practitioner,
			{"enable_free_follow_ups": 1, "max_visits": 2, "valid_days": 5},
		)

		# For first appointment, invoice is generated. First appointment not considered in fee validity
		appointment = create_appointment(patient, practitioner, nowdate())
		fee_validity = frappe.db.exists(
			"Fee Validity",
			{"patient": patient, "practitioner": practitioner, "patient_appointment": appointment.name},
		)
		invoiced = frappe.db.get_value("Patient Appointment", appointment.name, "invoiced")
		self.assertEqual(invoiced, 1)
		self.assertTrue(fee_validity)
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "status"), "Active")
		self.assertEqual(frappe.db.get_value("Fee Validity", fee_validity, "max_visits"), 2)

		start_date, valid_till = frappe.db.get_value(
			"Fee Validity", fee_validity, ["start_date", "valid_till"]
		)
		self.assertEqual(date_diff(valid_till, start_date), 5)
