"""Tests for the Multi-Depot Resource Allocation MILP Solver."""
import pulp
import pytest
from pydantic import BaseModel, Field
from typing import List, Dict, Tuple
from app import depots
from app.allocation import Depot, IncidentDemand, optimize_allocation

def test_simple_full_allocation():
    """Test that a single depot with enough capacity fully supplies a single incident."""
    depots = [Depot(id="D1", capacity=50, lat=26.18, lon=91.75)]
    incidents = [IncidentDemand(id="I1", severity_score=10.0, demand=20, lat=26.17, lon=91.77)]
    distances = {("I1", "D1"): 2.5}
    
    result = optimize_allocation(incidents, depots, distances)
    
    # Incident I1 should get exactly its demand (20) from Depot D1
    assert result["I1"]["D1"] == 20

def test_priority_allocation_under_capacity_constraints():
    """
    Test that when depot capacity is less than total demand, 
    the solver prioritizes the incident with the higher severity score (S_i).
    """
    depots = [Depot(id="D1", capacity=15, lat=26.18, lon=91.75)]
    incidents = [
        # Low severity, needs 10
        IncidentDemand(id="I_LOW", severity_score=2.0, demand=10, lat=26.17, lon=91.77),
        # High severity (CRITICAL), needs 10
        IncidentDemand(id="I_HIGH", severity_score=50.0, demand=10, lat=26.17, lon=91.77)
    ]
    distances = {("I_LOW", "D1"): 2.0, ("I_HIGH", "D1"): 2.0}
    
    result = optimize_allocation(incidents, depots, distances)
    
    # The solver should give all 10 needed to the high severity incident
    assert result["I_HIGH"]["D1"] == 10
    # The remaining 5 capacity goes to the low severity incident
    assert result["I_LOW"]["D1"] == 5

def test_distance_penalty_minimization():
    """
    Test that the solver prefers a closer depot over a farther depot 
    to minimize the transit penalty (c_ij).
    """
    depots = [
        Depot(id="D_CLOSE", capacity=50, lat=26.175, lon=91.775),
        Depot(id="D_FAR", capacity=50, lat=26.128, lon=91.800)
    ]
    incidents = [IncidentDemand(id="I1", severity_score=10.0, demand=30, lat=26.176, lon=91.776)]
    
    distances = {
        ("I1", "D_CLOSE"): 1.5,
        ("I1", "D_FAR"): 15.0
    }
    
    # Setting a high lambda penalty to ensure distance heavily impacts the objective function
    result = optimize_allocation(incidents, depots, distances, lambda_penalty=1.0)
    
    # All resources should come from the closer depot
    assert result["I1"]["D_CLOSE"] == 30
    assert result["I1"].get("D_FAR", 0) == 0

def test_demand_limit_enforcement():
    """Test that a depot does not send more resources than the incident actually demanded."""
    depots = [Depot(id="D1", capacity=100, lat=26.18, lon=91.75)]
    incidents = [IncidentDemand(id="I1", severity_score=5.0, demand=5, lat=26.17, lon=91.77)]
    distances = {("I1", "D1"): 2.5}
    
    result = optimize_allocation(incidents, depots, distances)
    
    # Even though depot has 100 capacity, it should only allocate exactly 5
    assert result["I1"]["D1"] == 5

def test_unreachable_allocation():
    """Test behavior when transit penalties severely outweigh triage utility."""
    depots = [Depot(id="D1", capacity=10, lat=26.18, lon=91.75)]
    # Very low severity incident
    incidents = [IncidentDemand(id="I1", severity_score=0.1, demand=10, lat=26.17, lon=91.77)]
    # Extremely far away (e.g., thousands of km)
    distances = {("I1", "D1"): 5000.0}
    
    result = optimize_allocation(incidents, depots, distances, lambda_penalty=10.0)
    
    # Cost to transport exceeds utility, so allocation should be 0
    assert result["I1"].get("D1", 0) == 0


def optimize_resource_allocation(
    incidents: List[dict],
    depots: List[Depot],
    distances: Dict[Tuple[str, str], float],
    lambda_penalty: float = 0.01,
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Allocate each requested resource from depot inventories.

    Returns:
    {
        "INC_1": {
            "Depot_ZooRoad": {"Inflatable Rafts": 2},
            "Depot_Dispur": {"First Aid Kits": 3}
        }
    }
    """
    prob = pulp.LpProblem(
        "Resource_Allocation",
        pulp.LpMaximize
    )

    x = {}

    # Create decision variables for every incident, depot and resource.
    for inc in incidents:
        for depot in depots:
            for resource in inc.get("needed_resources", []):
                resource_name = resource["item_name"]
                variable_name = f"x_{inc['id']}_{depot.id}_{resource_name}"

                x[(inc["id"], depot.id, resource_name)] = (
                    prob.add_variable(
                        variable_name,
                        lowBound=0,
                        cat=pulp.LpInteger
                    )
                )

    utility_terms = []
    penalty_terms = []

    for inc in incidents:
        for depot in depots:
            distance = distances.get((inc["id"], depot.id), 9999.0)

            for resource in inc.get("needed_resources", []):
                resource_name = resource["item_name"]
                var = x[(inc["id"], depot.id, resource_name)]

                utility_terms.append(inc["severity_score"] * var)
                penalty_terms.append(lambda_penalty * distance * var)

    prob += pulp.lpSum(utility_terms) - pulp.lpSum(penalty_terms)

    # Constraint 1: A depot cannot distribute more than its stock.
    # Constraint 1: A depot cannot distribute more than its stock.
    for depot in depots:
        for inc in incidents:
            for resource in inc.get("needed_resources", []):
                resource_name = resource["item_name"]
                stock = depot.inventory.get(resource_name, 0)

                prob += (
                    x[(inc["id"], depot.id, resource_name)] <= stock
                )

    # Constraint 2: An incident cannot receive more than it requested.
    for inc in incidents:
        for resource in inc.get("needed_resources", []):
            resource_name = resource["item_name"]
            incident_vars = [
                x[(inc["id"], depot.id, resource_name)]
                for depot in depots
            ]
            prob += pulp.lpSum(incident_vars) <= resource["quantity"]

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    allocation_plan = {inc["id"]: {} for inc in incidents}

    for inc in incidents:
        for depot in depots:
            depot_allocation = {}

            for resource in inc.get("needed_resources", []):
                resource_name = resource["item_name"]
                var = x[(inc["id"], depot.id, resource_name)]
                quantity = int(var.varValue or 0)

                if quantity > 0:
                    depot_allocation[resource_name] = quantity

            if depot_allocation:
                allocation_plan[inc["id"]][depot.id] = depot_allocation

    return allocation_plan
