# -*- encoding: utf-8 -*-

# Copyright (C) 2015-2016 Eric Goller <eric.goller@ninjaduck.solutions>

# This file is part of 'hamster-lib'.
#
# 'hamster-lib' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'hamster-lib' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'hamster-lib'.  If not, see <http://www.gnu.org/licenses/>.


"""
Module containing base classes intended to be inherited from when implementing storage backends.

Note:
    * This is propably going to be replaced by a ``ABC``-bases solution.
    * Basic sanity checks could be done here then. This would mean we just need to test
        them once and our actual backends focus on the CRUD implementation.
"""


from __future__ import absolute_import, unicode_literals

import copy
import datetime
import logging
import os
import pickle

import hamster_lib
from future.utils import python_2_unicode_compatible
from hamster_lib import objects
from hamster_lib.helpers import logging as logging_helpers
from hamster_lib.helpers import time as time_helpers
from hamster_lib.helpers import helpers


@python_2_unicode_compatible
class BaseStore(object):
    """
    A controller store provides unified interfaces to interact with our stored entities.

    ``self.logger`` provides a dedicated logger instance for any storage related logging.
    If you want to make use of it, just setup and attach your handlers and you are ready to go.
    Be advised though, ``self.logger`` will be very verbose as on ``debug`` it will log any
    method call and often even their returned instances.
    """

    def __init__(self, config):
        self.config = config
        self.init_logger()
        self.categories = BaseCategoryManager(self)
        self.activities = BaseActivityManager(self)
        self.tags = BaseTagManager(self)
        self.facts = BaseFactManager(self)

    def cleanup(self):
        """
        Any backend specific teardown code that needs to be executed before
        we shut down gracefully.
        """
        raise NotImplementedError

    def init_logger(self):
        self.logger = logging.getLogger('hamster_lib.storage')
        self.logger.addHandler(logging.NullHandler())

        warn_name = False
        try:
            sql_log_level = self.config['sql_log_level']
            try:
                log_level = int(sql_log_level)
            except ValueError:
                log_level = logging.getLevelName(sql_log_level)
        except KeyError:
            log_level = logging.WARNING
        try:
            self.logger.setLevel(int(log_level))
        except ValueError:
            warn_name = True
            log_level = logging.WARNING

        stream_handler = logging.StreamHandler()
        formatter = logging_helpers.formatter_basic()
        formatter = logging_helpers.setupHandler(stream_handler, formatter, self.logger)

        if warn_name:
            self.logger.warning('Unknown sql_log_level specified: {}'.format(sql_log_level))


@python_2_unicode_compatible
class BaseManager(object):
    """Base class for all object managers."""

    def __init__(self, store):
        self.store = store


@python_2_unicode_compatible
class BaseMigrationsManager(BaseManager):
    """Base class defining the minimal API for a MigrationsManager implementation."""

    def downgrade(self):
        """Downgrade the database according to its migration version."""
        raise NotImplementedError

    def upgrade(self):
        """Upgrade the database according to its migration version."""
        raise NotImplementedError

    def version(self):
        """Returns the migration version of the database indicated by the config."""
        raise NotImplementedError


@python_2_unicode_compatible
class BaseCategoryManager(BaseManager):
    """Base class defining the minimal API for a CategoryManager implementation."""

    def save(self, category):
        """
        Save a Category to our selected backend.
        Internal code decides whether we need to add or update.

        Args:
            category (hamster_lib.Category): Category instance to be saved.

        Returns:
            hamster_lib.Category: Saved Category

        Raises:
            TypeError: If the ``category`` parameter is not a valid ``Category`` instance.
        """

        if not isinstance(category, objects.Category):
            message = _("You need to pass a hamster category")
            self.store.logger.debug(message)
            raise TypeError(message)

        self.store.logger.debug(_("'{}' has been received.".format(category)))

        # We don't check for just ``category.pk`` because we don't want to make
        # assumptions about the PK being an int or being >0.
        if category.pk or category.pk == 0:
            result = self._update(category)
        else:
            result = self._add(category)
        return result

    def get_or_create(self, category):
        """
        Check if we already got a category with that name, if not create one.

        This is a convenience method as it seems sensible to rather implement
        this once in our controller than having every client implementation
        deal with it anew.

        It is worth noting that the lookup completely ignores any PK contained in the
        passed category. This makes this suitable to just create the desired Category
        and pass it along. One way or the other one will end up with a persisted
        db-backed version.

        Args:
            category (hamster_lib.Category or None): The categories.

        Returns:
            hamster_lib.Category or None: The retrieved or created category. Either way,
                the returned Category will contain all data from the backend, including
                its primary key.
        """

        self.store.logger.debug(_("'{}' has been received.'.".format(category)))
        if category:
            try:
                category = self.get_by_name(category)
            except KeyError:
                category = objects.Category(category)
                category = self._add(category)
        else:
            # We want to allow passing ``category=None``, so we normalize here.
            category = None
        return category

    def _add(self, category):
        """
        Add a ``Category`` to our backend.

        Args:
            category (hamster_lib.Category): ``Category`` to be added.

        Returns:
            hamster_lib.Category: Newly created ``Category`` instance.

        Raises:
            ValueError: When the category name was already present! It is supposed to be
            unique.
            ValueError: If category passed already got an PK. Indicating that update would
                be more appropriate.

        Note:
            * Legacy version stored the proper name as well as a ``lower(name)`` version
            in a dedicated field named ``search_name``.
        """
        raise NotImplementedError

    def _update(self, category):
        """
        Update a ``Categories`` values in our backend.

        Args:
            category (hamster_lib.Category): Category to be updated.

        Returns:
            hamster_lib.Category: The updated Category.

        Raises:
            KeyError: If the ``Category`` can not be found by the backend.
            ValueError: If the ``Category().name`` is already being used by
                another ``Category`` instance.
            ValueError: If category passed does not have a PK.
        """
        raise NotImplementedError

    def remove(self, category):
        """
        Remove a category.

        Any ``Activity`` referencing the passed category will be set to
        ``Activity().category=None``.

        Args:
            category (hamster_lib.Category): Category to be updated.

        Returns:
            None: If everything went ok.

        Raises:
            KeyError: If the ``Category`` can not be found by the backend.
            TypeError: If category passed is not an hamster_lib.Category instance.
            ValueError: If category passed does not have an pk.
        """
        raise NotImplementedError

    def get(self, pk):
        """
        Get an ``Category`` by its primary key.

        Args:
            pk (int): Primary key of the ``Category`` to be fetched.

        Returns:
            hamster_lib.Category: ``Category`` with given primary key.

        Raises:
            KeyError: If no ``Category`` with this primary key can be found by the backend.
        """

        raise NotImplementedError

    def get_by_name(self, name):
        """
        Look up a category by its name.

        Args:
            name (str): Unique name of the ``Category`` to we want to fetch.

        Returns:
            hamster_lib.Category: ``Category`` with given name.

        Raises:
            KeyError: If no ``Category`` with this name was found by the backend.
        """
        raise NotImplementedError

    def get_all(self, **kwargs):
        """
        Return a list of all categories.

        Returns:
            list: List of ``Categories``, ordered by ``lower(name)``.
        """
        raise NotImplementedError


@python_2_unicode_compatible
class BaseActivityManager(BaseManager):
    """Base class defining the minimal API for a ActivityManager implementation."""
    def save(self, activity):
        """
        Save a ``Activity`` to the backend.

        This public method decides if it calls either ``_add`` or ``_update``.

        Args:
            activity (hamster_lib.Activity): ``Activity`` to be saved.

        Returns:
            hamster_lib.Activity: The saved ``Activity``.
        """

        self.store.logger.debug(_("'{}' has been received.".format(activity)))
        if activity.pk or activity.pk == 0:
            result = self._update(activity)
        else:
            result = self._add(activity)
        return result

    def get_or_create(self, activity):
        """
        Convenience method to either get an activity matching the specs or create a new one.

        Args:
            activity (hamster_lib.Activity): The activity we want.

        Returns:
            hamster_lib.Activity: The retrieved or created activity
        """
        self.store.logger.debug(_("'{}' has been received.".format(activity)))
        try:
            activity = self.get_by_composite(activity.name, activity.category)
        except KeyError:
            activity = self.save(hamster_lib.Activity(activity.name, category=activity.category,
                deleted=activity.deleted))
        return activity

    def _add(self, activity):
        """
        Add a new ``Activity`` instance to the database.

        Args:
            activity (hamster_lib.Activity): The ``Activity`` to be added.

        Returns:
            hamster_lib.Activity: The newly created ``Activity``.

        Raises:
            ValueError: If the passed activity has a PK.
            ValueError: If the category/activity.name combination to be added is
                already present in the db.

        Note:
            According to ``storage.db.Storage.__add_activity``: when adding a new activity
            with a new category, this category does not get created but instead this
            activity.category=None. This makes sense as categories passed are just ids, we
            however can pass full category objects. At the same time, this approach allows
            to add arbitrary category.id as activity.category without checking their existence.
            this may lead to db anomalies.
        """
        raise NotImplementedError

    def _update(self, activity):
        """
        Update values for a given activity.

        Which activity to refer to is determined by the passed PK new values
        are taken from passed activity as well.

        Args:
            activity (hamster_lib.Activity): Activity to be updated.

        Returns:
            hamster_lib.Activity: Updated activity.
        Raises:
            ValueError: If the new name/category.name combination is already taken.
            ValueError: If the the passed activity does not have a PK assigned.
            KeyError: If the the passed activity.pk can not be found.

        Note:
            Seems to modify ``index``.
        """

        raise NotImplementedError

    def remove(self, activity):
        """
        Remove an ``Activity`` from the database.import

        If the activity to be removed is associated with any ``Fact``-instances,
        we set ``activity.deleted=True`` instead of deleting it properly.
        If it is not, we delete it from the backend.

        Args:
            activity (hamster_lib.Activity): The activity to be removed.

        Returns:
            bool: True

        Raises:
            KeyError: If the given ``Activity`` can not be found in the database.

        Note:
            Should removing the last activity of a category also trigger category
            removal?
        """

        raise NotImplementedError

    def get(self, pk):
        """
        Return an activity based on its primary key.

        Args:
            pk (int): Primary key of the activity

        Returns:
            hamster_lib.Activity: Activity matching primary key.

        Raises:
            KeyError: If the primary key can not be found in the database.
        """
        raise NotImplementedError

    def get_by_composite(self, name, category):
        """
        Lookup for unique 'name/category.name'-composite key.

        This method utilizes that to return the corresponding entry or None.

        Args:
            name (str): Name of the ``Activities`` in question.
            category (hamster_lib.Category or None): ``Category`` of the activities. May be None.

        Returns:
            hamster_lib.Activity: The corresponding activity

        Raises:
            KeyError: If the composite key can not be found.
        """
        # [FIXME]
        # Handle resurrection. See legacy
        # ``hamster.sorage.db.__get_activity_by_name``

        raise NotImplementedError

    def get_all(self, category=False, search_term='', sort_by_column='', **kwargs):
        """
        Return all matching activities.

        Args:
            category (hamster_lib.Category, optional): Limit activities to this category.
                Defaults to ``False``. If ``category=None`` only activities without a
                category will be considered.
            search_term (str, optional): Limit activities to those matching this string
                a substring in their name. Defaults to ``empty string``.

        Returns:
            list: List of ``hamster_lib.Activity`` instances matching constrains. This list
                is ordered by ``Activity.name``.

        Note:
            * This method combines legacy ``storage.db.__get_activities`` and
                ``storage.db.____get_category_activities``.
            * Can search terms be prefixed with 'not'?
            * Original implementation in ``hamster.storage.db.__get_activities`` returns
                activity names converted to lowercase!
            * Does exclude activities with ``deleted=True``.
        """
        # [FIXME]
        # ``__get_category_activity`` order by lower(activity.name),
        # ``__get_activities```orders by most recent start date *and*
        # lower(activity.name).
        raise NotImplementedError

    def get_all_by_usage(self, category=False, search_term='', sort_by_column='', **kwargs):
        """
        Similar to get_all(), but include count of Facts that reference each Activity.
        """
        raise NotImplementedError


@python_2_unicode_compatible
class BaseTagManager(BaseManager):
    """Base class defining the minimal API for a TagManager implementation."""

    def save(self, tag):
        """
        Save a Tag to our selected backend.
        Internal code decides whether we need to add or update.

        Args:
            tag (hamster_lib.Tag): Tag instance to be saved.

        Returns:
            hamster_lib.Tag: Saved Tag

        Raises:
            TypeError: If the ``tag`` parameter is not a valid ``Tag`` instance.
        """

        if not isinstance(tag, objects.Tag):
            message = _("You need to pass a hamster tag")
            self.store.logger.debug(message)
            raise TypeError(message)

        self.store.logger.debug(_("'{}' has been received.".format(tag)))

        # We don't check for just ``tag.pk`` because we don't want to make
        # assumptions about the PK being an int or being >0.
        if tag.pk or tag.pk == 0:
            result = self._update(tag)
        else:
            result = self._add(tag)
        return result

    def get_or_create(self, tag):
        """
        Check if we already got a tag with that name, if not create one.

        This is a convenience method as it seems sensible to rather implement
        this once in our controller than having every client implementation
        deal with it anew.

        It is worth noting that the lookup completely ignores any PK contained in the
        passed tag. This makes this suitable to just create the desired Tag
        and pass it along. One way or the other one will end up with a persisted
        db-backed version.

        Args:
            tag (hamster_lib.Tag or None): The categories.

        Returns:
            hamster_lib.Tag or None: The retrieved or created tag. Either way,
                the returned Tag will contain all data from the backend, including
                its primary key.
        """

        self.store.logger.debug(_("'{}' has been received.'.".format(tag)))
        if tag:
            try:
                tag = self.get_by_name(tag)
            except KeyError:
                tag = objects.Tag(tag)
                tag = self._add(tag)
        else:
            # We want to allow passing ``tag=None``, so we normalize here.
            tag = None
        return tag

    def _add(self, tag):
        """
        Add a ``Tag`` to our backend.

        Args:
            tag (hamster_lib.Tag): ``Tag`` to be added.

        Returns:
            hamster_lib.Tag: Newly created ``Tag`` instance.

        Raises:
            ValueError: When the tag name was already present! It is supposed to be
            unique.
            ValueError: If tag passed already got an PK. Indicating that update would
                be more appropriate.
        """
        raise NotImplementedError

    def _update(self, tag):
        """
        Update a ``Tags`` values in our backend.

        Args:
            tag (hamster_lib.Tag): Tag to be updated.

        Returns:
            hamster_lib.Tag: The updated Tag.

        Raises:
            KeyError: If the ``Tag`` can not be found by the backend.
            ValueError: If the ``Tag().name`` is already being used by
                another ``Tag`` instance.
            ValueError: If tag passed does not have a PK.
        """
        raise NotImplementedError

    def remove(self, tag):
        """
        Remove a tag.

        Any ``Fact`` referencing the passed tag will have this tag removed.

        Args:
            tag (hamster_lib.Tag): Tag to be updated.

        Returns:
            None: If everything went ok.

        Raises:
            KeyError: If the ``Tag`` can not be found by the backend.
            TypeError: If tag passed is not an hamster_lib.Tag instance.
            ValueError: If tag passed does not have an pk.
        """
        raise NotImplementedError

    def get(self, pk):
        """
        Get an ``Tag`` by its primary key.

        Args:
            pk (int): Primary key of the ``Tag`` to be fetched.

        Returns:
            hamster_lib.Tag: ``Tag`` with given primary key.

        Raises:
            KeyError: If no ``Tag`` with this primary key can be found by the backend.
        """

        raise NotImplementedError

    def get_by_name(self, name):
        """
        Look up a tag by its name.

        Args:
            name (str): Unique name of the ``Tag`` to we want to fetch.

        Returns:
            hamster_lib.Tag: ``Tag`` with given name.

        Raises:
            KeyError: If no ``Tag`` with this name was found by the backend.
        """
        raise NotImplementedError

    def get_all(
        self,
        search_term='',
        sort_by_name=False,
        sort_by_use=False,
        **kwargs
    ):
        """
        Get all tags, with filtering and sorting options.

        Returns:
            list: List of all Tags present in the database,
                  ordered by lower(name), or most recently
                  used; possibly filtered by a search term.
        """
        raise NotImplementedError


@python_2_unicode_compatible
class BaseFactManager(BaseManager):
    """Base class defining the minimal API for a FactManager implementation."""
    def save(self, fact):
        """
        Save a Fact to our selected backend.

        Unlike the private ``_add`` and ``_update`` methods, ``save`` enforces that
        the config given ``fact_min_delta`` is enforced.

        Args:
            fact (hamster_lib.Fact): Fact to be saved. Needs to be complete otherwise
            this will fail.

        Returns:
            hamster_lib.Fact: Saved Fact.

        Raises:
            ValueError: If ``fact.delta`` is smaller than ``self.store.config['fact_min_delta']``-
        """
        self.store.logger.debug(_("Fact: '{}' has been received.".format(fact)))

        fact_min_delta = datetime.timedelta(seconds=int(self.store.config['fact_min_delta']))

        if fact.delta and (fact.delta < fact_min_delta):
            message = _(
                "The passed facts delta is shorter than the mandatory value of {} seconds"
                " specified in your config.".format(fact_min_delta)
            )
            self.store.logger.error(message)
            raise ValueError(message)

        if fact.pk or fact.pk == 0:
            result = self._update(fact)
        elif fact.end is None:
            result = self._start_tmp_fact(fact)
        else:
            result = self._add(fact)
        return result

    def _add(self, fact):
        """
        Add a new ``Fact`` to the backend.

        Args:
            fact (hamster_lib.Fact): Fact to be added.

        Returns:
            hamster_lib.Fact: Added ``Fact``.

        Raises:
            ValueError: If the passed fact has a PK assigned. New facts should not have one.
            ValueError: If the timewindow is already occupied.
        """
        raise NotImplementedError

    def _update(self, fact):
        """
        Update and existing fact with new values.

        Args:
            fact (hamster_lib.fact): Fact instance holding updated values.

        Returns:
            hamster_lib.fact: Updated Fact

        Raises:
            KeyError: if a Fact with the relevant PK could not be found.
            ValueError: If the the passed activity does not have a PK assigned.
            ValueError: If the timewindow is already occupied.
        """
        raise NotImplementedError

    def remove(self, fact):
        """
        Remove a given ``Fact`` from the backend.

        Args:
            fact (hamster_lib.Fact): ``Fact`` instance to be removed.

        Returns:
            bool: Success status

        Raises:
            ValueError: If fact passed does not have an pk.
            KeyError: If the ``Fact`` specified could not be found in the backend.
        """
        raise NotImplementedError

    def get(self, pk):
        """
        Return a Fact by its primary key.

        Args:
            pk (int): Primary key of the ``Fact to be retrieved``.

        Returns:
            hamster_lib.Fact: The ``Fact`` corresponding to the primary key.

        Raises:
            KeyError: If primary key not found in the backend.
        """
        raise NotImplementedError

    def get_all(
        self,
        start=None,
        end=None,
        filter_term='',
        order='desc',
        **kwargs
    ):
        """
        Return all facts within a given timeframe (beginning of start_date
        end of end_date) that match given search terms.

        Args:
            start_date (datetime.datetime, optional): Consider only Facts starting at or after
                this date. Alternatively you can also pass a ``datetime.datetime`` object
                in which case its own time will be considered instead of the default ``day_start``
                or a ``datetime.time`` which will be considered as today.
                Defaults to ``None``.
            end_date (datetime.datetime, optional): Consider only Facts ending before or at
                this date. Alternatively you can also pass a ``datetime.datetime`` object
                in which case its own time will be considered instead of the default ``day_start``
                or a ``datetime.time`` which will be considered as today.
                Defaults to ``None``.
            filter_term (str, optional): Only consider ``Facts`` with this string as part of their
                associated ``Activity.name``

        Returns:
            list: List of ``Facts`` matching given specifications.

        Raises:
            TypeError: If ``start`` or ``end`` are not ``datetime.date``, ``datetime.time`` or
                ``datetime.datetime`` objects.
            ValueError: If ``end`` is before ``start``.

        Note:
            * This public function only provides some sanity checks and normalization. The actual
                backend query is handled by ``_get_all``.
            * ``search_term`` should be prefixable with ``not`` in order to invert matching.
            * This does only return proper facts and does not include any existing 'ongoing fact'.
            * This method will *NOT* return facts that start before and end after
              (e.g. that span more than) the specified timeframe.
        """
        self.store.logger.debug(_(
            "Start: '{start}', end: {end} with filter: {filter} has been received.".format(
                start=start, end=end, filter=filter_term)
        ))

        if start is not None:
            if isinstance(start, datetime.datetime):
                # isinstance(datetime.datetime, datetime.date) returns True,
                # which is why we need to catch this case first.
                pass
            elif isinstance(start, datetime.date):
                start = datetime.datetime.combine(start, self.store.config['day_start'])
            elif isinstance(start, datetime.time):
                start = datetime.datetime.combine(datetime.date.today(), start)
            else:
                message = _(
                    "You need to pass either a datetime.date, datetime.time or datetime.datetime"
                    " object."
                )
                self.store.logger.debug(message)
                raise TypeError(message)

        if end is not None:
            if isinstance(end, datetime.datetime):
                # isinstance(datetime.datetime, datetime.date) returns True,
                # which is why we need to except this case first.
                pass
            elif isinstance(end, datetime.date):
                end = time_helpers.end_day_to_datetime(end, self.store.config)
            elif isinstance(end, datetime.time):
                end = datetime.datetime.combine(datetime.date.today(), end)
            else:
                message = _(
                    "You need to pass either a datetime.date, datetime.time or datetime.datetime"
                    " object."
                )
                raise TypeError(message)

        if start and end and (end <= start):
            message = _("End value can not be earlier than start!")
            self.store.logger.debug(message)
            raise ValueError(message)

        return self._get_all(
            start, end, filter_term, order=order, limit=limit, offset=offset,
        )

    def _get_all(
        self,
        start=None,
        end=None,
        search_terms='',
        partial=False,
        order='desc',
        **kwargs
    ):
        """
        Return a list of ``Facts`` matching given criteria.

        Args:
            start_date (datetime.datetime, optional): Consider only Facts starting at or after
                this datetime. Defaults to ``None``.
            end_date (datetime.datetime): Consider only Facts ending before or at
                this datetime. Defaults to ``None``.
            search_term (text_type): Cases insensitive strings to match
                ``Activity.name`` or ``Category.name``.
            partial (bool): If ``False`` only facts which start *and* end
                within the timeframe will be considered.

        Returns:
            list: List of ``Facts`` matching given specifications.

        Note:
            In contrast to the public ``get_all``, this method actually handles the
            backend query.
        """
        raise NotImplementedError

    def get_today(self):
        """
        Return all facts for today, while respecting ``day_start``.

        Returns:
            list: List of ``Fact`` instances.

        Note:
            * This does only return proper facts and does not include any existing 'ongoing fact'.
        """
        self.store.logger.debug(_("Returning today's facts"))

        today = datetime.date.today()
        return self.get_all(
            datetime.datetime.combine(today, self.store.config['day_start']),
            time_helpers.end_day_to_datetime(today, self.store.config),
        )

    def _start_tmp_fact(self, fact):
        """
        Store new ongoing fact in persistent tmp file

        Args:
            fact (hamster_lib.Fact): Fact to be stored.

        Returns:
            hamster_lib.Fact: Fact stored.

        Raises:
            ValueError: If we already have a ongoing fact running.
            ValueError: If the fact passed does have an end and hence does not
                qualify for an 'ongoing fact'.
        """
        self.store.logger.debug(_("Fact: '{}' has been received.".format(fact)))
        if fact.end:
            message = _("The passed fact has an end specified.")
            self.store.logger.debug(message)
            raise ValueError(message)

        tmp_fact = helpers._load_tmp_fact(self._get_tmp_fact_path())
        if tmp_fact:
            message = _("Trying to start with ongoing fact already present.")
            self.store.logger.debug(message)
            raise ValueError(message)
        else:
            with open(self._get_tmp_fact_path(), 'wb') as fobj:
                pickle.dump(fact, fobj)
            self.store.logger.debug(_("New temporary fact started."))
        return fact

    def update_tmp_fact(self, fact):
        """
        Update an ongoing fact.

        Args:
            fact (hamster_lib.Fact): Fact with new values.

        Returns:
            fact (hamster_lib.Fact): The updated ``Fact`` instance.

        Raises:
            TypeError: If passed fact is not an instance of ``hamster_lib.Fact``.
            ValueError: If passed fact already has an ``end`` value and hence is
                not a valid *ongoing fact*.
        """
        if not isinstance(fact, hamster_lib.Fact):
            raise TypeError(_(
                "Passed fact is not a proper instance of 'hamster_lib.Fact'."
            ))

        if fact.end:
            raise ValueError(_(
                "The passed fact seems to have an end and hence is an invalid"
                " 'ongoing fact'."
            ))
        old_fact = self.get_tmp_fact()

        for attribute in ('activity', 'start', 'description', 'tags'):
            value = getattr(fact, attribute)
            setattr(old_fact, attribute, value)

        with open(self._get_tmp_fact_path(), 'wb') as fobj:
            pickle.dump(old_fact, fobj)
        self.store.logger.debug(_("Temporary fact updated."))

        return old_fact

    def stop_tmp_fact(self, end_hint=None):
        """
        Stop current 'ongoing fact'.

        Args:
            end_hint (datetime.timedelta or datetime.datetime, optional): Hint to be
                considered when setting ``Fact.end``. If no hint is provided
                ``Fact.end`` will be ``datetime.datetime.now()``. If a ``datetime`` is
                provided, this will be used as ``Fact.end`` value. If a ``timedelta``
                is provided it will be added to ``datetime.datetime.now()``.
                If you want the computed ``end`` to be *before* ``now()``
                you can pass negative ``timedelta`` values. Defaults to None.

        Returns:
            hamster_lib.Fact: The stored fact.

        Raises:
            TypeError: If ``end_hint`` is not a ``datetime.datetime`` or
                ``datetime.timedelta`` instance or ``None``.
            ValueError: If there is no currently 'ongoing fact' present.
            ValueError: If the final end value (due to the hint) is before
                the fact's start value.
        """
        self.store.logger.debug(_("Stopping 'ongoing fact'."))

        if not ((end_hint is None) or isinstance(end_hint, datetime.datetime) or (
                isinstance(end_hint, datetime.timedelta))):
            raise TypeError(_(
                "The 'end_hint' you passed needs to be either a"
                "'datetime.datetime' or 'datetime.timedelta' instance."
            ))

        if end_hint:
            if isinstance(end_hint, datetime.datetime):
                end = end_hint
            else:
                end = datetime.datetime.now() + end_hint
        else:
            end = datetime.datetime.now()

        fact = helpers._load_tmp_fact(self._get_tmp_fact_path())
        if fact:
            if fact.start > end:
                raise ValueError(_("The indicated 'end' value seem to be before its 'start'."))
            else:
                fact.end = end
            result = self.save(fact)
            os.remove(self._get_tmp_fact_path())
            self.store.logger.debug(_("Temporary fact stopped."))
        else:
            message = _("Trying to stop a non existing ongoing fact.")
            self.store.logger.debug(message)
            raise ValueError(message)
        return result

    def get_tmp_fact(self):
        """
        Provide a way to retrieve any existing 'ongoing fact'.

        Returns:
            hamster_lib.Fact: An instance representing our current 'ongoing fact'.capitalize

        Raises:
            KeyError: If no ongoing fact is present.
        """
        self.store.logger.debug(_("Trying to get 'ongoing fact'."))

        fact = helpers._load_tmp_fact(self._get_tmp_fact_path())
        if not fact:
            message = _("Tried to retrieve an 'ongoing fact' when there is none present.")
            self.store.logger.debug(message)
            raise KeyError(message)
        return fact

    def cancel_tmp_fact(self):
        """
        Provide a way to stop an 'ongoing fact' without saving it in the backend.

        Returns:
            None: If everything worked as expected.

        Raises:
            KeyError: If no ongoing fact is present.
        """
        # [TODO]
        # Maybe it would be useful to return the canceled fact instead. So it
        # would be available to clients. Otherwise they may be tempted to look
        # it up before canceling. which would result in two retrievals.
        self.store.logger.debug(_("Trying to cancel 'ongoing fact'."))

        fact = helpers._load_tmp_fact(self._get_tmp_fact_path())
        if not fact:
            message = _("Trying to stop a non existing ongoing fact.")
            self.store.logger.debug(message)
            raise KeyError(message)
        os.remove(self._get_tmp_fact_path())
        self.store.logger.debug(_("Temporary fact stoped."))

    def _get_tmp_fact_path(self):
        """Convenience function to assemble the tmpfile_path from config settings."""
        return self.store.config['tmpfile_path']

    # FIXME/2018-05-12: (lb): insert_forcefully does not respect tmp_fact!
    def insert_forcefully(self, fact):
        """
        Insert the possibly open-ended Fact into the set of logical
        (chronological) Facts, possibly changing the time frames of,
        or removing, other Facts.

        Args:
            fact (hamster_lib.Fact):
                The Fact to insert, with either or both ``start`` and ``end`` set.

        Returns:
            list: List of ``Facts``, ordered by ``start``.

        Raises:
            ValueError: If start or end time is not specified and cannot be
                deduced by other Facts in the system.
        """
        # Steps:
        #   Find fact overlapping start.
        #   Find fact overlapping end.
        #   Find facts wholly contained between start and end.
        #   Return unique set of facts indicating edits and deletions.

        def _insert_forcefully(facts, fact):
            conflicts = []
            conflicts += find_conflict(facts, fact, 'start')
            conflicts += find_conflict(facts, fact, 'end')
            if fact.start and fact.end:
                conflicts += facts.strictly_during(fact.start, fact.end)
            resolve_overlapping(fact, conflicts)
            return conflicts

        def find_conflict(facts, fact, ref_time):
            conflicts = []
            find_edge = False
            fact_time = getattr(fact, ref_time)
            if fact_time:  # fact.start or fact.end
                conflicts = facts.surrounding(fact_time)
                conflicts = [(fact, copy.deepcopy(fact)) for fact in conflicts]
                if not conflicts:
                    find_edge = True
            else:
                find_edge = True
            if find_edge:
                conflicts = inspect_time_boundary(facts, fact, ref_time)
            return conflicts

        def inspect_time_boundary(facts, fact, ref_time):
            conflict = None
            if ref_time == 'start':
                if fact.start is None:
                    set_start_per_antecedent(facts, fact)
                else:
                    conflict = facts.starting_at(fact)
            else:
                assert ref_time == 'end'
                if fact.end is None:
                    set_end_per_subsequent(facts, fact)
                else:
                    conflict = facts.ending_at(fact)
            conflicts = [(conflict, copy.deepcopy(conflict))] if conflict else []
            return conflicts

        # FIXME/2018-05-12: (lb): insert_forcefully does not respect tmp_fact!
        #   if 'hamster-to', and tmp fact, then start now, and end tmp_fact.
        #   if 'hamster-from', and tmp fact, then either close tmp at now,
        #     or at from time, or complain (add to conflicts) if overlapped.
        def set_start_per_antecedent(facts, fact):
            assert fact.start is None
            # Find a Fact with start < fact.end.
            ref_fact = facts.antecedent(fact)
            if not ref_fact:
                raise ValueError(_(
                    'Please specify `start` for fact being added before time existed.'
                ))
            # Because we called surrounding and got nothing,
            # we know that found_fact.end < fact.end,
            # so we can set fact.start accordingly.
            assert ref_fact.end < fact.end
            fact.start = ref_fact.end

        def set_end_per_subsequent(facts, fact):
            assert fact.end is None
            ref_fact = facts.subsequent(fact)
            if not ref_fact:
                # FIXME/MAYBE: (lb): Probably want to set to 'now' automatically?
                raise ValueError(_(
                    'Please specify `end` for fact being added after time existed.'
                ))
            assert ref_fact.start > fact.start
            fact.end = ref_fact.start

        def resolve_overlapping(fact, conflicts):
            seen = set()
            resolved = []
            for conflict, original in conflicts:
                assert conflict.pk > 0
                if conflict.pk in seen:
                    next
                seen.add(conflict.pk)
                resolved += resolve_fact_conflict(fact, conflict)
            return resolved

        def resolve_fact_conflict(fact, conflict):
            resolved = []
            if fact.start <= conflict.start:
                resolve_fact_starts_before(fact, conflict, resolved)
            elif fact.end >= conflict.end:
                resolve_fact_ends_after(fact, conflict, resolved)
            else:
                # The new fact is contained *within* the conflict!
                resolve_fact_is_inside(fact, conflict, resolved)
            return resolved

        def resolve_fact_starts_before(fact, conflict, resolved):
            if fact.end >= conflict.end:
                conflict.deleted = True
                conflict.dirty_reasons.add('deleted')
            else:
                assert conflict.start < fact.end
                conflict.start = fact.end
                conflict.dirty_reasons.add('start')
            resolved.append(conflict)

        def resolve_fact_ends_after(fact, conflict, resolved):
            assert fact.start < conflict.end
            conflict.end = fact.start
            conflict.dirty_reasons.add('end')
            resolved.append(conflict)

        def resolve_fact_is_inside(fact, conflict, resolved):
            resolve_fact_split_prior(fact, conflict, resolved)
            resolve_fact_split_after(fact, conflict, resolved)

        def resolve_fact_split_prior(fact, conflict, resolved):
            lconflict = copy.deepcopy(conflict)
            lconflict.end = fact.start
            lconflict.dirty_reasons.add('end')
            resolved.append(lconflict)

        def resolve_fact_split_after(fact, conflict, resolved):
            rconflict = copy.deepcopy(conflict)
            rconflict.start = fact.end
            rconflict.dirty_reasons.add('start')
            resolved.append(rconflict)

        # The actual insert_forcefully function.

        return _insert_forcefully(self, fact)

    def starting_at(self, fact):
        """
        Return the fact starting at the moment in time indicated by fact.start.

        Args:
            fact (hamster_lib.Fact):
                The Fact to reference, with its ``start`` set.

        Returns:
            hamster_lib.Fact: The found Fact, or None if none found.

        Raises:
            IntegrityError: If more than one Fact found at given time.
        """
        raise NotImplementedError

    def ending_at(self, fact):
        """
        Return the fact ending at the moment in time indicated by fact.end.

        Args:
            fact (hamster_lib.Fact):
                The Fact to reference, with its ``end`` set.

        Returns:
            hamster_lib.Fact: The found Fact, or None if none found.

        Raises:
            IntegrityError: If more than one Fact found at given time.
        """
        raise NotImplementedError

    def antecedent(self, fact):
        """
        Return the Fact immediately preceding the indicated Fact.

        Args:
            fact (hamster_lib.Fact):
                The Fact to reference, with its ``start`` set.

        Returns:
            hamster_lib.Fact: The antecedent Fact, or None if none found.

        Raises:
            ValueError: If neither ``start`` nor ``end`` is set on fact.
        """
        raise NotImplementedError

    def subsequent(self, fact):
        """
        Return the Fact immediately following the indicated Fact.

        Args:
            fact (hamster_lib.Fact):
                The Fact to reference, with its ``end`` set.

        Returns:
            hamster_lib.Fact: The subsequent Fact, or None if none found.

        Raises:
            ValueError: If neither ``start`` nor ``end`` is set on fact.
        """
        raise NotImplementedError

    def strictly_during(self, start, end, result_limit=10):
        """
        Return the fact(s) strictly contained within a start and end time.

        Args:
            start (datetime.datetime):
                Start datetime of facts to find.

            end (datetime.datetime):
                End datetime of facts to find.

            result_limit (int):
                Maximum number of facts to find, else raise OverflowError.

        Returns:
            list: List of ``hamster_lib.Facts`` instances.
        """
        raise NotImplementedError

    def surrounding(self, fact_time):
        """
        Return the fact(s) at the given moment in time.
        Note that this excludes a fact that starts or ends at this time.
        (See antecedent and subsequent for finding those facts.)

        Args:
            fact_time (datetime.datetime):
                Time of fact(s) to match.

        Returns:
            list: List of ``hamster_lib.Facts`` instances.

        Raises:
            IntegrityError: If more than one Fact found at given time.
        """
        raise NotImplementedError


# ***
# *** Helper functions.
# ***


def _query_apply_limit_offset(query, **kwargs):
    """
    Applies 'limit' and 'offset' to the database fetch query

    On applies 'limit' if specified; and only applies 'offset' if specified.

    Args:
        query (???): Query (e.g., return from self.store.session.query(...))

        kwargs (keyword arguments):
            limit (int|str, optional): Limit to apply to the query.

            offset (int|str, optional): Offset to apply to the query.

    Returns:
        list: The query passed in, modified with limit and/or offset, maybe.
    """
    raise NotImplementedError

