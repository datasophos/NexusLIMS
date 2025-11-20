"""
A representation of calendar reservations.

This module contains a class to represent calendar reservations and
associated metadata harvest metadata from various calendar sources.
The expectation is that submodules of this module will have a method named
``res_event_from_session`` implemented to handle fetching a ReservationEvent
object from a :py:class:`nexusLIMS.db.session_handler.Session` object.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List

from lxml import etree

from nexusLIMS.instruments import Instrument


@dataclass
class ReservationEvent:
    """
    A representation of a single calendar reservation.

    The representation is independent of the type of calendar the reservation was
    made with. ``ReservationEvent`` is a common interface that is used by the record
    building code.

    Any attribute can be None to indicate it was not present or no value was
    provided. The :py:meth:`as_xml` method is used to serialize the information
    contained within a ``ReservationEvent`` into an XML representation that is
    compatible with the Nexus Facility ``Experiment`` schema.

    Attributes
    ----------
    experiment_title
        The title of the event
    instrument
        The instrument associated with this reservation
    last_updated : datetime.datetime
        The time this event was last updated
    username
        The username of the user indicated in this event
    user_full_name
        The full name of the user for this event
    created_by
        The username of the user that created this event
    created_by_full_name
        The full name of the user that created this event
    start_time
        The time this event was scheduled to start
    end_time
        The time this event was scheduled to end
    reservation_type
        The "type" or category of this event (such as User session, service,
        etc.))
    experiment_purpose
        The user-entered purpose of this experiment
    sample_details
        A list of the user-entered sample details for this experiment. The
        length of the list must match that given in ``sample_pid`` and
        ``sample_name``.
    sample_pid
        A list of sample PIDs provided by the user. The
        length of the list must match that given in ``sample_details`` and
        ``sample_name``.
    sample_name
        A list of user-friendly sample names (not a PID). The
        length of the list must match that given in ``sample_details`` and
        ``sample_pid``.
    project_name
        A list of the user-entered project names for this experiment. The
        length of the list must match that given in ``project_id`` and
        ``project_ref``.
    project_id
        A list of the specific project IDs within a research group/division. The
        length of the list must match that given in ``project_name`` and
        ``project_ref``.
    project_ref
        A list of (optional) links to this project in another database. The
        length of the list must match that given in ``project_name`` and
        ``project_id``.
    internal_id
        The identifier assigned to this event (if any) by the calendaring system
    division
        An identifier of the division this experiment was performed for (i.e.
        the user's division)
    group
        An identifier of the group this experiment was performed for (i.e.
        the user's group)
    url
        A web-accessible link to a summary of this reservation
    """

    experiment_title: str | None = None
    instrument: Instrument | None = None
    last_updated: datetime | None = None
    username: str | None = None
    user_full_name: str | None = None
    created_by: str | None = None
    created_by_full_name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    reservation_type: str | None = None
    experiment_purpose: str | None = None
    sample_details: List[str | None] | None = None
    sample_pid: List[str | None] | None = None
    sample_name: List[str | None] | None = None
    sample_elements: List[List[str] | None] | None = None
    project_name: List[str | None] | None = None
    project_id: List[str | None] | None = None
    project_ref: List[str | None] | None = None
    internal_id: str | None = None
    division: str | None = None
    group: str | None = None
    url: str | None = None

    def __post_init__(self):
        """Post-initialization to coerce arguments to lists and validate."""
        # coerce sample arguments into lists
        self.sample_details = (
            self.sample_details
            if isinstance(self.sample_details, list)
            else [self.sample_details]
        )
        self.sample_pid = (
            self.sample_pid if isinstance(self.sample_pid, list) else [self.sample_pid]
        )
        self.sample_name = (
            self.sample_name
            if isinstance(self.sample_name, list)
            else [self.sample_name]
        )
        # sample elements should be a list of List[str] or None; we shouldn't really be
        # doing the above coercion anyway, so we'll assume the caller knows what
        # they're doing and used the right argument type
        if self.sample_elements is None:
            self.sample_elements = [None]

        # coerce project arguments into lists
        self.project_name = (
            self.project_name
            if isinstance(self.project_name, list)
            else [self.project_name]
        )
        self.project_id = (
            self.project_id if isinstance(self.project_id, list) else [self.project_id]
        )
        self.project_ref = (
            self.project_ref
            if isinstance(self.project_ref, list)
            else [self.project_ref]
        )

        # raise error if all sample values are not none and have different
        # lengths (this shouldn't happen):
        self._check_arg_lists()

    def _check_arg_lists(self):
        for check_name, arg_names, lists in zip(
            ["sample", "project"],
            [
                "[sample_details, sample_pid, sample_name]",
                "[project_name, project_id, project_ref]",
            ],
            [
                [self.sample_details, self.sample_pid, self.sample_name],
                [self.project_name, self.project_id, self.project_ref],
            ],
        ):
            if all(x is not None for x in lists):
                length = len(lists[0])
                if not all(len(lst) == length for lst in lists[1:]):
                    msg = (
                        f"Length of {check_name} arguments must be the same. The "
                        "lengths of the following arguments were "
                        f"{arg_names} : "
                        f"{[len(list_) for list_ in lists]}"
                    )
                    raise ValueError(msg)

    def __repr__(self):
        """Return custom representation of a ReservationEvent."""
        if self.username and self.start_time and self.end_time:
            return (
                f"Event for {self.username} on {self.instrument.name} "
                f"from "
                f"{self.instrument.localize_datetime(self.start_time).isoformat()} "
                f"to {self.instrument.localize_datetime(self.end_time).isoformat()}"
            )
        return "No matching calendar event" + (
            f" for {self.instrument.name}" if self.instrument else ""
        )

    def as_xml(self) -> etree.Element:
        """
        Get an XML representation of this ReservationEvent.

        Returns
        -------
        root : lxml.etree.Element
            The reservation event serialized as XML that matches the
            Nexus Experiment schema
        """
        root = etree.Element("root")

        # top-level nodes
        title_el = etree.SubElement(root, "title")
        if self.experiment_title:
            title_el.text = self.experiment_title
        else:
            title_el.text = f"Experiment on the {self.instrument.schema_name}"
            if self.start_time:
                title_el.text += f" on {self.start_time.strftime('%A %b. %d, %Y')}"
        if self.internal_id:
            id_el = etree.SubElement(root, "id")
            id_el.text = self.internal_id

        # summary node
        root = self._add_summary_node(root)

        # sample nodes
        root = self._add_sample_nodes(root)

        # project nodes
        return self._add_project_nodes(root)

    def _add_summary_node(self, root):
        summary_el = etree.SubElement(root, "summary")
        if self.user_full_name:
            experimenter_el = etree.SubElement(summary_el, "experimenter")
            experimenter_el.text = self.user_full_name
        elif self.username:
            experimenter_el = etree.SubElement(summary_el, "experimenter")
            experimenter_el.text = self.username
        if self.instrument:
            instr_el = etree.SubElement(summary_el, "instrument")
            instr_el.text = self.instrument.schema_name
            pid = self.instrument.name
            # temporary workaround for duplicate harvesters for some instruments
            if self.instrument.harvester == "nemo" and self.instrument.name.endswith(
                "_n",
            ):  # pragma: no cover
                pid = self.instrument.name.strip("_n")
            instr_el.set("pid", pid)
        if self.start_time:
            start_el = etree.SubElement(summary_el, "reservationStart")
            if self.instrument is not None:
                start_el.text = self.instrument.localize_datetime(
                    self.start_time,
                ).isoformat()
            else:
                start_el.text = self.start_time.isoformat()
        if self.end_time:
            end_el = etree.SubElement(summary_el, "reservationEnd")
            if self.instrument is not None:
                end_el.text = self.instrument.localize_datetime(
                    self.end_time,
                ).isoformat()
            else:
                end_el.text = self.end_time.isoformat()
        if self.experiment_purpose:
            motivation_el = etree.SubElement(summary_el, "motivation")
            motivation_el.text = self.experiment_purpose
        if self.url:
            summary_el.set("ref", self.url)

        return root

    def _add_sample_nodes(self, root):
        if self.sample_pid is not None:
            # if any of the sample arguments are not none, they should be
            # lists, so we should create a sample element for each one
            for pid, name, details, elements in zip(
                self.sample_pid,
                self.sample_name,
                self.sample_details,
                self.sample_elements,
            ):
                # create one sample subelement for each sample in our lists
                sample_el = etree.SubElement(root, "sample")
                if pid is not None:
                    sample_el.set("ref", pid)
                if name is not None:
                    sample_name_el = etree.SubElement(sample_el, "name")
                    sample_name_el.text = name
                if details is not None:
                    sample_detail_el = etree.SubElement(sample_el, "description")
                    sample_detail_el.text = details
                if elements is not None:
                    sample_elements_el = etree.SubElement(sample_el, "elements")
                    for element in elements:
                        etree.SubElement(sample_elements_el, element)
        return root

    def _add_project_nodes(self, root):
        if self.project_name is not None:
            for name, pid, ref in zip(
                self.project_name,
                self.project_id,
                self.project_ref,
            ):
                project_el = etree.SubElement(root, "project")
                if name is not None:
                    project_name_el = etree.SubElement(project_el, "name")
                    project_name_el.text = name
                if self.division is not None:
                    division_el = etree.SubElement(project_el, "division")
                    division_el.text = self.division
                if self.group is not None:
                    group_el = etree.SubElement(project_el, "group")
                    group_el.text = self.group
                if pid is not None:
                    proj_id_el = etree.SubElement(project_el, "project_id")
                    proj_id_el.text = pid
                if ref is not None:
                    proj_ref_el = etree.SubElement(project_el, "ref")
                    proj_ref_el.text = ref

        return root
