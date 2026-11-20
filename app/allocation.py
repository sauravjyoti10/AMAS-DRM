"""Multi-Depot Resource Allocation MILP Solver."""
import pulp
from pydantic import BaseModel, Field
from typing import List, Dict, Tuple

# Transit penalty used by the live pipeline. Found by evaluation/eval_allocation.py: with the old 0.1, a LOW incident
# (severity weight 1) more than 10 km from a depot had a NEGATIVE utility, so it received nothing even while stock sat idle.
# Keeping lambda * (longest realistic trip, ~30 km) below the smallest severity weight (1.0) makes distance a tie-breaker only.
PIPELINE_TRANSIT_PENALTY = 0.01


class Depot(BaseModel):
    id: str
    name: str = ""
    capacity: int
    lat: float
    lon: float
    inventory: Dict[str, int] = Field(default_factory=dict)

class IncidentDemand(BaseModel):
    id: str
    severity_score: float  # S_i from your PPT
    demand: int
    lat: float
    lon: float

def optimize_allocation(
    incidents: List[IncidentDemand], 
    depots: List[Depot], 
    distances: Dict[Tuple[str, str], float], 
    lambda_penalty: float = 0.1
) -> Dict[str, Dict[str, int]]:
    
    # 1. Initialize Problem
    prob = pulp.LpProblem("Emergency_Resource_Allocation", pulp.LpMaximize)
    
    # 2. Decision Variables (Using the API we proved works in your environment)
    x = {}
    for inc in incidents:
        for dep in depots:
            var_name = f"x_{inc.id}_{dep.id}"
            # This executed flawlessly on your machine previously
            x[(inc.id, dep.id)] = prob.add_variable(var_name, lowBound=0, cat=pulp.LpInteger)
            
    # 3. Objective Function: Maximize Utility - Transit Penalty
    utility_terms = []
    penalty_terms = []
    for inc in incidents:
        for dep in depots:
            var = x[(inc.id, dep.id)]
            utility_terms.append(inc.severity_score * var)
            dist = distances.get((inc.id, dep.id), 9999.0)
            penalty_terms.append(lambda_penalty * dist * var)
            
    prob += pulp.lpSum(utility_terms) - pulp.lpSum(penalty_terms)
    
    # 4. Constraints
    # Depot Capacity Limit
    for dep in depots:
        depot_vars = [x[(inc.id, dep.id)] for inc in incidents]
        prob += (pulp.lpSum(depot_vars) <= dep.capacity, f"Cap_{dep.id}")
        
    # Incident Demand Limit
    for inc in incidents:
        inc_vars = [x[(inc.id, dep.id)] for dep in depots]
        prob += (pulp.lpSum(inc_vars) <= inc.demand, f"Dem_{inc.id}")
        
    # 5. Solve (Using the empty call we proved bypasses the PULP_CBC_CMD error)
    prob.solve()
    
    # 6. Parse and return results
    allocation_plan = {inc.id: {} for inc in incidents}
    for inc in incidents:
        for dep in depots:
            var = x[(inc.id, dep.id)]
            allocated_qty = int(var.varValue or 0)
            if allocated_qty > 0:
                allocation_plan[inc.id][dep.id] = allocated_qty
                
    return allocation_plan


def optimize_resource_allocation(
    incidents: List[dict],
    depots: List[Depot],
    distances: Dict[Tuple[str, str], float],
    lambda_penalty: float = 0.01,
) -> Dict[str, Dict[str, Dict[str, int]]]:

    prob = pulp.LpProblem("Resource_Allocation", pulp.LpMaximize)
    x = {}

    for inc in incidents:
        for depot in depots:
            for resource in inc.get("needed_resources", []):
                name = resource["item_name"]
                x[(inc["id"], depot.id, name)] = prob.add_variable(
                    f"x_{inc['id']}_{depot.id}_{name}",
                    lowBound=0,
                    cat=pulp.LpInteger,
                )

    utility_terms = []
    penalty_terms = []

    for inc in incidents:
        for depot in depots:
            distance = distances.get((inc["id"], depot.id), 9999.0)

            for resource in inc.get("needed_resources", []):
                name = resource["item_name"]
                var = x[(inc["id"], depot.id, name)]

                utility_terms.append(inc["severity_score"] * var)
                penalty_terms.append(lambda_penalty * distance * var)

    prob += pulp.lpSum(utility_terms) - pulp.lpSum(penalty_terms)

    # Depot inventory constraints.
    
# Depot inventory constraints: stock is shared across all incidents.
    resource_names = {
        resource["item_name"]
        for inc in incidents
        for resource in inc.get("needed_resources", [])
    }

    for depot in depots:
        for name in resource_names:
            depot_vars = [
                x[(inc["id"], depot.id, name)]
                for inc in incidents
                if any(
                    resource["item_name"] == name
                    for resource in inc.get("needed_resources", [])
                )
            ]

            prob += (
                pulp.lpSum(depot_vars) <= depot.inventory.get(name, 0)
            )


    # Incident demand constraints.
    for inc in incidents:
        for resource in inc.get("needed_resources", []):
            name = resource["item_name"]

            prob += pulp.lpSum(
                x[(inc["id"], depot.id, name)]
                for depot in depots
            ) <= resource["quantity"]

    prob.solve()

    allocation_plan = {inc["id"]: {} for inc in incidents}

    for inc in incidents:
        for depot in depots:
            depot_allocation = {}

            for resource in inc.get("needed_resources", []):
                name = resource["item_name"]
                quantity = int(x[(inc["id"], depot.id, name)].varValue or 0)

                if quantity > 0:
                    depot_allocation[name] = quantity

            if depot_allocation:
                allocation_plan[inc["id"]][depot.id] = depot_allocation

    return allocation_plan
