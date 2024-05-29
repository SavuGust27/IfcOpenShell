# BlenderBIM Add-on - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>
#
# This file is part of BlenderBIM Add-on.
#
# BlenderBIM Add-on is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BlenderBIM Add-on is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BlenderBIM Add-on.  If not, see <http://www.gnu.org/licenses/>.

from types import ClassMethodDescriptorType
import bpy
import blenderbim.core.tool
import blenderbim.tool as tool
import ifcopenshell
from mathutils import Vector
from ifcopenshell import util
import ifcopenshell.util.unit
import ifcopenshell.util.element
from blenderbim.bim.module.pset.qto_calculator import QtoCalculator, QuanityTypes
from blenderbim.bim.module.pset.calc_quantity_function_mapper import mapper
import blenderbim.bim.schema
from typing import Optional, Union, Literal


class Qto(blenderbim.core.tool.Qto):
    @classmethod
    def get_radius_of_selected_vertices(cls, obj: bpy.types.Object) -> float:
        selected_verts = [v.co for v in obj.data.vertices if v.select]
        total = Vector()
        for v in selected_verts:
            total += v
        circle_center = total / len(selected_verts)
        return max([(v - circle_center).length for v in selected_verts])

    @classmethod
    def set_qto_result(cls, result: float) -> None:
        bpy.context.scene.BIMQtoProperties.qto_result = str(round(result, 3))

    @classmethod
    def add_object_base_qto(cls, obj: bpy.types.Object) -> Union[ifcopenshell.entity_instance, None]:
        product = tool.Ifc.get_entity(obj)
        return cls.add_product_base_qto(product)

    @classmethod
    def add_product_base_qto(cls, product: ifcopenshell.entity_instance) -> Union[ifcopenshell.entity_instance, None]:
        base_quantity_name = cls.get_applicable_base_quantity_name(product)
        if base_quantity_name:
            return tool.Ifc.run(
                "pset.add_qto",
                product=product,
                name=base_quantity_name,
            )

    @classmethod
    def get_applicable_quantity_names(cls, qto_name: str) -> list[str]:
        pset_template = blenderbim.bim.schema.ifc.psetqto.get_by_name(qto_name)
        return (
            [property.Name for property in pset_template.HasPropertyTemplates]
            if hasattr(pset_template, "HasPropertyTemplates")
            else []
        )

    @classmethod
    def get_applicable_base_quantity_name(
        cls, product: Optional[ifcopenshell.entity_instance] = None
    ) -> Union[str, None]:
        if not product:
            return
        applicable_qto_names = blenderbim.bim.schema.ifc.psetqto.get_applicable_names(
            product.is_a(), ifcopenshell.util.element.get_predefined_type(product), qto_only=True
        )
        # See https://github.com/buildingSMART/IFC4.3.x-development/issues/851 for anomalies in Qto naming
        # Should be in sync with cls.get_base_qto.
        applicable_qto: Union[str, None] = None
        for qto_name in applicable_qto_names:
            # No need for "Qto_" check since we use qto_only=True.
            if "Base" in qto_name:
                return qto_name
            # Prioritize anomaly named base quantities over Qto_BodyGeometryValidation.
            if applicable_qto and "BodyGeometryValidation" not in applicable_qto:
                continue
            applicable_qto = qto_name
        return applicable_qto

    @classmethod
    def get_new_calculated_quantity(cls, qto_name: str, quantity_name: str, obj: bpy.types.Object) -> float:
        return QtoCalculator().calculate_quantity(qto_name, quantity_name, obj)

    @classmethod
    def get_rounded_value(cls, new_quantity: float) -> float:
        return round(new_quantity, 3)

    @classmethod
    def get_calculated_object_quantities(
        cls, calculator: QtoCalculator, qto_name: str, obj: bpy.types.Object
    ) -> dict[str, float]:
        return {
            quantity_name: cls.get_rounded_value(value)
            for quantity_name in cls.get_applicable_quantity_names(qto_name) or []
            if cls.has_calculator(qto_name, quantity_name)
            and (value := calculator.calculate_quantity(qto_name, quantity_name, obj)) is not None
        }

    @classmethod
    def has_calculator(cls, qto_name: str, quantity_name: str) -> bool:
        return bool(mapper.get(qto_name, {}).get(quantity_name, None))

    @classmethod
    def convert_to_project_units(
        cls,
        value: float,
        qto_name: Optional[str] = None,
        quantity_name: Optional[str] = None,
        quantity_type: Optional[QuanityTypes] = None,
    ) -> Union[float, None]:
        """You can either specify `quantity_type` or provide `qto_name/quantity_name`
        to let method figure the `quantity_type` from the templates
        """
        ifc_file = tool.Ifc.get()
        quantity_to_unit_types = {
            "Q_LENGTH": ("LENGTHUNIT", "METRE"),
            "Q_AREA": ("AREAUNIT", "SQUARE_METRE"),
            "Q_VOLUME": ("VOLUMEUNIT", "CUBIC_METRE"),
        }
        if not quantity_type:
            qt = blenderbim.bim.schema.ifc.psetqto.get_by_name(qto_name)
            quantity_type = next(q.TemplateType for q in qt.HasPropertyTemplates if q.Name == quantity_name)

        unit_type = quantity_to_unit_types.get(quantity_type, None)
        if not unit_type:
            return

        unit_type, base_unit = unit_type
        project_unit = ifcopenshell.util.unit.get_project_unit(ifc_file, unit_type)
        if not project_unit:
            return
        value = ifcopenshell.util.unit.convert(
            value,
            from_prefix=None,
            from_unit=base_unit,
            to_prefix=getattr(project_unit, "Prefix", None),
            to_unit=project_unit.Name,
        )
        return value

    @classmethod
    def get_base_qto(cls, product: ifcopenshell.entity_instance) -> Union[ifcopenshell.entity_instance, None]:
        if not hasattr(product, "IsDefinedBy"):
            return
        # Should be in sync with cls.get_applicable_base_quantity_name.
        base_qto_definition = None
        base_qto_definition_name: Union[str, None] = None
        for rel in product.IsDefinedBy or []:
            definition = rel.RelatingPropertyDefinition
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            definition = rel.RelatingPropertyDefinition
            definition_name = definition.Name
            if "Qto_" not in definition_name:
                continue
            if "Base" in definition_name:
                return definition
            if base_qto_definition and "BodyGeometryValidation" not in base_qto_definition_name:
                continue
            base_qto_definition = definition
            base_qto_definition_name = definition_name
        return base_qto_definition

    @classmethod
    def get_related_cost_item_quantities(cls, product: ifcopenshell.entity_instance) -> list[dict]:
        """_summary_: Returns the related cost item and related quantities of the product

        :param ifc-instance product: ifc instance
        :type product: ifcopenshell.entity_instance.entity_instance

        :return list of dictionaries in the form [
        {
        "cost_item_id" : XX,
        "cost_item_name" : XX,
        "quantity_id" : XX,
        "quantity_name" : XX,
        "quantity_value" : XX,
        "quantity_type" : XX
        }]
        :rtype: list

        Example:

        .. code::Python
        import blenderbim.tool as tool

        relating_cost_items = tool.Qto.relating_cost_items(my_beautiful_wall)
        for relating_cost_item in relating_cost_items:
            print(f"RELATING COST ITEM NAME: {relating_cost_item["cost_item_name"]}")
            print(f"RELATING COST QUANTITY NAME: {relating_cost_item["quantity_name"]}")
            ...
        """
        model = tool.Ifc.get()
        cost_items = model.by_type("IfcCostItem")
        result = []
        base_qto = cls.get_base_qto(product)
        quantities = base_qto.Quantities if base_qto else []

        for cost_item in cost_items:
            cost_item_quantities = cost_item.CostQuantities if cost_item.CostQuantities is not None else []
            for cost_item_quantity in cost_item_quantities:
                for quantity in quantities:
                    if quantity == cost_item_quantity:
                        result.append(
                            {
                                "cost_item_id": cost_item.id(),
                                "cost_item_name": cost_item.Name,
                                "quantity_id": quantity.id(),
                                "quantity_name": quantity.Name,
                                "quantity_value": quantity[3],
                                "quantity_type": quantity.is_a(),
                            }
                        )
        return result
