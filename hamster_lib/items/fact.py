# -*- encoding: utf-8 -*-

# This file is part of 'hamster-lib'.
#
# 'hamster-lib' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'hamster-lib' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'hamster-lib'. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import datetime
from collections import namedtuple
from operator import attrgetter

from future.utils import python_2_unicode_compatible
from hamster_lib.helpers import time as time_helpers
from hamster_lib.helpers.helpers import parse_raw_fact
from six import text_type


FactTuple = namedtuple('FactTuple', ('pk', 'activity', 'start', 'end', 'description', 'tags'))


@python_2_unicode_compatible
class Fact(object):
    """Storage agnostic class for facts."""
    # [TODO]
    # There is some weird black magic still to be integrated from
    # ``store.db.Storage``. Among it ``__get_facts()``.
    #

    def __init__(
        self,
        activity,
        start,
        end=None,
        pk=None,
        description=None,
        tags=None,
    ):
        """
        Initiate our new instance.

        Args:
            activity (hamster_lib.Activity): Activity associated with this fact.
            start (datetime.datetime): Start datetime of this fact.
            end (datetime.datetime, optional): End datetime of this fact. Defaults to ``None``.
            pk (optional): Primary key used by the backend to identify this instance. Defaults
                to ``None``.
            description (str, optional): Additional information relevant to this singular fact.
                Defaults to ``None``.
            tags (Iterable, optional): Iterable of ``strings`` identifying *tags*. Defaults to
                ``None``.

        Note:
            * For ``start`` and ``end``: Seconds will be stored, but are ignored for all
            intends and purposes.
        """

        self.pk = pk
        self.activity = activity
        self.start = start
        self.end = end
        self.description = description
        # AUDIT/2018-05-05: From a scientificsteve branch (but no PR:
        # he had a PR against the CLI, and then I found his branch with
        # corresponding changes to the LIB that were not PR'ed!). The
        # original code uses a set of strings; so I'm a little nervous
        # changing to a list of Tags....
        #
        #   self.tags = set()
        #   if tags:
        #       self.tags = set(tags)
        #
        self.tags = []
        if tags:
            tags = set(tags)
            self.tags = [Tag(name=tagname) for tagname in tags]

    @classmethod
    def create_from_raw_fact(
        cls, raw_fact, config=None,
    ):
        """
        Construct a new ``hamster_lib.Fact`` from a ``raw fact`` string.

        Please note that this just handles the parsing and construction of a new
        Fact including *new* ``Category`` and ``Activity`` instances.
        It will require a separate step to check this against the backend in order
        to figure out if those probably already exist!

        This approach has the benefit of providing this one single point of entry.
        Once any such raw fact has been turned in to a proper ``hamster_lib.Fact``
        we can rely on it having encapsulated all.

        As a consequence extra care has to be taken to mask/escape them.

        Args:
            raw_fact (str): Raw fact to be parsed.
            config (dict, optional): Controller config provided additional settings
                relevant for timeframe completion.

        Returns:
            hamster_lib.Fact: ``Fact`` object with data parsed from raw fact.

        Raises:
            ValueError: If we fail to extract at least ``start`` or ``activity.name``.
            ValueError: If ``end <= start``.

        """

        if not config:
            config = {'day_start': datetime.time(0, 0, 0)}

        extracted_components = parse_raw_fact(raw_fact)

        start, end = time_helpers.complete_timeframe(extracted_components['timeinfo'],
            config, partial=True)
        # Please note that start/end may very well be ``None`` due to the
        # partial completion!
        start, end = time_helpers.validate_start_end_range((start, end))

        activity_name = extracted_components['activity']
        if activity_name:
            activity = Activity(activity_name)
        else:
            raise ValueError(_('Unable to extract activity name'))

        category_name = extracted_components['category']
        if category_name:
            activity.category = Category(category_name)

        description = extracted_components['description']

        tags = extracted_components['tags']

        return cls(
            activity, start, end=end, description=description, tags=tags,
        )

    @property
    def start(self):
        return self._start

    @property
    def end(self):
        return self._end

    @property
    def start_ftime(self):
        try:
            return self._start.strftime("%Y-%m-%d %H:%M:%S")
        except AttributeError:
            return ''

    @property
    def end_ftime(self):
        try:
            return self._end.strftime("%Y-%m-%d %H:%M:%S")
        except AttributeError:
            return ''

    @start.setter
    def start(self, start):
        """
        Make sure that we receive a ``datetime.datetime`` instance.

        Args:
            start (datetime.datetime): Start datetime of this ``Fact``.

        Raises:
            TypeError: If we receive something other than a ``datetime.datetime`` (sub-)class
            or ``None``.
        """

        if start:
            if not isinstance(start, datetime.datetime):
                raise TypeError(_(
                    "You need to pass a ``datetime.datetime`` instance!"
                    " {type} instance received instead.".format(type=type(start))
                ))
        else:
            start = None
        self._start = start

    @end.setter
    def end(self, end):
        """
        Make sure that we receive a ``datetime.datetime`` instance.

        Args:
            end (datetime.datetime): End datetime of this ``Fact``.

        Raises:
            TypeError: If we receive something other than a ``datetime.datetime`` (sub-)class
            or ``None``.
        """

        if end:
            if not isinstance(end, datetime.datetime):
                raise TypeError(_(
                    "You need to pass a ``datetime.datetime`` instance!"
                    " {type} instance received instead.".format(type=type(end))
                ))
        else:
            end = None
        self._end = end

    @property
    def delta(self):
        """
        Provide the offset of start to end for this fact.

        Returns:
            datetime.timedelta or None: Difference between start- and end datetime.
                If we only got a start datetime, return ``None``.
        """
        result = None
        if self.end:
            result = self.end - self.start
        return result

    def get_string_delta(self, format='%M'):
        """
        Return a string representation of ``Fact().delta``.

        Args:
            format (str): Specifies the output format. Valid choices are:
                * ``'%M'``: As minutes, rounded down.
                * ``'%H:%M'``: As 'hours:minutes'. rounded down.

        Returns:
            str: String representing this facts *duration* in the given format.capitalize

        Raises:
            ValueError: If a unrecognized format specifier is received.
        """
        seconds = int(self.delta.total_seconds())
        # MAYBE/2018-05-05: (lb): scientificsteve rounds instead of floors.
        # I'm not sure this is correct. The user only commented in the commit,
        #   "Round the minutes instead of flooring." But they did not bother to
        #   edit the docstring above, which explicitly says that time is rounded
        #   down!
        # So I'm making a note of this -- because I incorporated the tags feature
        #   from scientificsteve's PR -- but I did not incorporate the rounding
        #   change. For one, I am not sure what uses this function, so I don't
        #   feel confident changing it.
        # See:
        #   SHA 369050067485636475cd38d2cc8f38aaf58a3932
        if format == '%M':
            result = text_type(int(seconds / 60))
            # From scientificsteve's PR:
            #  result = text_type(int(round(seconds / 60.)))
        elif format == '%H:%M':
            result = '{hours:02d}:{minutes:02d}'.format(hours=int(seconds / 3600),
                minutes=int((seconds % 3600) / 60))
            # From scientificsteve's PR:
            #  result = '{hours:02d}:{minutes:02d}'.format(hours=int(round(seconds / 3600.)),
            #      minutes=int(round((seconds % 3600.) / 60.)))
        else:
            raise ValueError(_("Got invalid format argument."))
        return result

    @property
    def date(self):
        """
        Return the date the fact has started.

        Returns:
            datetime.datetime: The date the fact has started.

        Note:
            This is merely a convenience / legacy property to stay in line with
            *legacy hamster*.
        """
        return self.start.date()

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, description):
        """"
        Normalize all descriptions that evaluate to ``False``. Store everything else as string.
        """
        if description:
            description = text_type(description)
        else:
            description = None
        self._description = description

    @property
    def activity_name(self):
        """..."""
        try:
            return self.activity.name
        except AttributeError:
            return ''

    @property
    def category(self):
        """For convenience only."""
        # (lb): Whose convenience? If this DRYs code, it's for that, too. =)
        return self.activity.category

    @property
    def category_name(self):
        """..."""
        try:
            return self.activity.category.name
        except AttributeError:
            return ''

    @property
    def tags_sorted(self):
        # MAYBE: (lb): Which version of sorted is preferred?
        #
        # Test, e.g., 10K iterations:
        #
        #   return sorted(self.tags, key=lambda tag: tag.name)
        #
        # vs.
        #
        #   return sorted(list(self.tags), key=attrgetter('name'))
        #
        # Not that we'd ever have that many tags. I'm just curious.
        return sorted(list(self.tags), key=attrgetter('name'))

    def tagnames(self, fmttr=lambda x: x):
        # NOTE: Return string includes leading space if nonempty!
        tagnames = ''
        if self.tags:
            ordered_tagnames = [
                fmttr('#{}'.format(tag.name)) for tag in self.tags_sorted
            ]
            tagnames = ' {}'.format(' '.join(ordered_tagnames))
        return tagnames

    def get_serialized_string(self):
        """
        Provide a canonical 'stringified' version of the fact.

        This is different from ``__str__`` as we may change what information is
        to be included in ``__str__`` anytime (and we may use localization
        etc ..) but this property guarantees that all relevant values will be
        encoded in the returned string in a canonical way. In that regard it
        is in a way a counterpart to ``Fact.create_from_raw_fact``.
        This also serves as a go-to reference implementation for 'what does a
        complete ``raw fact`` looks like'.

        Please be advised though that the ``raw_string`` used to create a
        ``Fact`` instance is not necessarily identical to this instance's
        ``serialized_string`` as the ``raw fact`` string may omit certain
        values which will be autocompleted while this property always returns
        a *complete* string.

        A complete serialized fact looks like this:
            ``2016-02-01 17:30 - 2016-02-01 18:10 making plans@world domination
            #tag 1 #tag 2, description``

            Please note that we are very liberal with allowing whitespace
            for ``Activity.name`` and ``Category.name``.

        Attention:
            ``Fact.tags`` is a set and hence unordered. In order to provide
            a deterministic canonical return string we will sort tags by name
            and list them alphabetically. This is purely cosmetic and does not
            imply any actual ordering of those facts on the instance level.

        Returns:
            text_type: Canonical string encoding all available fact info.
        """
        def get_times_string(fact):
            if fact.start:
                if fact.end:
                    result = '{start} - {end} '.format(
                        start=fact.start.strftime('%Y-%m-%d %H:%M'),
                        end=fact.end.strftime('%Y-%m-%d %H:%M')
                    )
                else:
                    result = '{} '.format(fact.start.strftime('%Y-%m-%d %H:%M'))
            else:
                result = ''
            return result

        def get_activity_string(fact):
            if fact.category:
                result = '{a.name}@{a.category.name}'.format(a=fact.activity)
            else:
                result = '{}'.format(fact.activity.name)
            return result

        tags = self.tagnames()

        description = ''
        if self.description:
            description = ', {}'.format(self.description)

        result = '{times}{activity}{tags}{description}'.format(
            times=get_times_string(self),
            activity=get_activity_string(self),
            tags=tags,
            description=description
        )

        return text_type(result)

    def as_tuple(self, include_pk=True):
        """
        Provide a tuple representation of this facts relevant attributes.

        Args:
            include_pk (bool): Whether to include the instances pk or not. Note that if
            ``False`` ``tuple.pk = False``!

        Returns:
            hamster_lib.FactTuple: Representing this categories values.
        """
        pk = self.pk
        if not include_pk:
            pk = False

        ordered_tags = [
            tag.as_tuple(include_pk=include_pk) for tag in self.tags_sorted
        ]

        return FactTuple(
            pk,
            self.activity.as_tuple(include_pk=include_pk),
            self.start,
            self.end,
            self.description,
            frozenset(ordered_tags),
        )

    def equal_fields(self, other):
        """
        Compare this instances fields with another fact. This excludes comparing the PK.

        Args:
            other (Fact): Fact to compare this instance with.

        Returns:
            bool: ``True`` if all fields but ``pk`` are equal, ``False`` if not.

        Note:
            This is particularly useful if you want to compare a new ``Fact`` instance
            with a freshly created backend instance. As the latter will probably have a
            primary key assigned now and so ``__eq__`` would fail.
        """
        return self.as_tuple(include_pk=False) == other.as_tuple(include_pk=False)

    def __eq__(self, other):
        if not isinstance(other, FactTuple):
            other = other.as_tuple()

        return self.as_tuple() == other

    def __hash__(self):
        """Naive hashing method."""
        return hash(self.as_tuple())

    def __str__(self):
        return self.friendly_str(text_type)

    def __repr__(self):
        return self.friendly_str(repr)

    def friendly_str(self, fmttr):
        result = fmttr(self.activity.name)

        if self.category:
            result += "@%s" % fmttr(self.category.name)

        result += self.tagnames(fmttr)

        if self.description:
            result += ', {}'.format(fmttr(self.description) or '')

        if self.start:
            start = fmttr(self.start.strftime("%Y-%m-%d %H:%M:%S"))

        if self.end:
            end = fmttr(self.end.strftime("%Y-%m-%d %H:%M:%S"))

        if self.start and self.end:
            result = '{} to {} {}'.format(start, end, result)
        elif self.start and not self.end:
            result = '{} {}'.format(start, result)

        if fmttr != repr:
            return fmttr(result)
        else:
            return str(result)

    def friendly_diff(self, other, fmttr=text_type):
        result = ''
        result += self.diff_other(other, 'start', 'start_ftime')
        result += self.diff_other(other, 'end', 'end_ftime')
        result += self.diff_other(other, 'activity', 'activity_name')
        result += self.diff_other(other, 'category', 'category_name')
        result += self.diff_other(other, 'tags', 'tags_sorted')
        result += self.diff_other(other, 'description', 'description')
        return result

    def diff_other(self, other, name, prop):
        prefix = '  '
        self_val = getattr(self, prop)
        other_val = getattr(other, prop)
        if self_val != other_val:
            self_val = '{}{}{}'.format(
                fg('spring_green_3a'), self_val, attr('reset'),
            )
            other_val = ' => {}{}{}{}{}'.format(
                attr('bold'), attr('underlined'), fg('light_salmon_3b'), other_val, attr('reset'),
            )
        else:
            other_val = ''
        attr_diff = '{}{:.<19} : {}{}\n'.format(
            prefix, name, self_val, other_val,
        )
        return attr_diff
