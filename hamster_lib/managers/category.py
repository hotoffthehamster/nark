# -*- coding: utf-8 -*-

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

from __future__ import absolute_import, unicode_literals
from future.utils import python_2_unicode_compatible

from . import BaseManager
from ..items.category import Category


@python_2_unicode_compatible
class BaseCategoryManager(BaseManager):
    """
    Base class defining the minimal API for a CategoryManager implementation.
    """

    def __init__(self, *args, **kwargs):
        super(BaseCategoryManager, self).__init__(*args, **kwargs)

    # ***

    def save(self, category):
        """
        Save a Category to our selected backend.
        Internal code decides whether we need to add or update.

        Args:
            category (hamster_lib.Category): Category instance to be saved.

        Returns:
            hamster_lib.Category: Saved Category

        Raises:
            TypeError: If the ``category`` parameter is not a valid
                ``Category`` instance.
        """

        if not isinstance(category, Category):
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

    # ***

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
                category = Category(category)
                category = self._add(category)
        else:
            # We want to allow passing ``category=None``, so we normalize here.
            category = None
        return category

    # ***

    def _add(self, category):
        """
        Add a ``Category`` to our backend.

        Args:
            category (hamster_lib.Category): ``Category`` to be added.

        Returns:
            hamster_lib.Category: Newly created ``Category`` instance.

        Raises:
            ValueError: When the category name was already present!
                It is supposed to be unique.
            ValueError: If category passed already got an PK.
                Indicating that update would be more appropriate.

        Note:
            * Legacy version stored the proper name as well as a ``lower(name)`` version
            in a dedicated field named ``search_name``.
        """
        raise NotImplementedError

    # ***

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

    # ***

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

    # ***

    def get(self, pk):
        """
        Get an ``Category`` by its primary key.

        Args:
            pk (int): Primary key of the ``Category`` to be fetched.

        Returns:
            hamster_lib.Category: ``Category`` with given primary key.

        Raises:
            KeyError: If no ``Category`` with this primary key can be found
                by the backend.
        """

        raise NotImplementedError

    # ***

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

    # ***

    def get_all(
        self,
        include_usage=True,
        deleted=False,
        hidden=False,
        search_term='',
        activity=False,
        sort_col='',
        sort_order='',
        limit='',
        offset='',
    ):
        """
        Return a list of all categories.

        Returns:
            list: List of ``Categories``, ordered by ``lower(name)``.
        """
        raise NotImplementedError

