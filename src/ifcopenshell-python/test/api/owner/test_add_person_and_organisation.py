# IfcOpenShell - IFC toolkit and geometry engine
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>
#
# This file is part of IfcOpenShell.
#
# IfcOpenShell is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# IfcOpenShell is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with IfcOpenShell.  If not, see <http://www.gnu.org/licenses/>.

import test.bootstrap
import ifcopenshell.api.owner


class TestAddPersonAndOrganisation(test.bootstrap.IFC4):
    def test_adding(self):
        person = self.file.createIfcPerson()
        organisation = self.file.createIfcOrganization()
        ifcopenshell.api.owner.add_person_and_organisation(
            self.file, person=person, organisation=organisation
        )


class TestAddPersonAndOrganisationIFC2X3(test.bootstrap.IFC2X3, TestAddPersonAndOrganisation):
    pass
