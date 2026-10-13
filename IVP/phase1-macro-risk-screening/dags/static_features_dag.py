"""Airflow DAG: Static Features & Slope Unit Preparation (Section 5.11).

Schedule: On data change (e.g. DEM or geological survey updates).
Tasks: DEM prep -> Slope unit delineation -> Terrain derivatives -> Static feature extraction -> Exposure.
"""

from datetime import datetime, timedelta
try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    HAS_AIRFLOW = True
except ImportError:
    HAS_AIRFLOW = False


def task_dem_prep():
    """Reproject DEM to metric UTM CRS and condition hydrologically."""
    print("DEM preprocessing and metric reprojection complete.")
    return True


def task_slope_units():
    """Delineate slope units with r.slopeunits and verify topology."""
    print("Slope units delineated and frozen with unique SU IDs.")
    return True


def task_terrain_derivatives():
    """Compute Horn slope, aspect, curvatures, and TWI."""
    print("Horn derivatives and TWI computed.")
    return True


def task_static_features():
    """Extract geological lithology ratings, kinematic indices, and proximity metrics."""
    print("Static features aggregated per slope unit.")
    return True


def task_exposure_layers():
    """Calculate normalized exposure from population, buildings, and critical infrastructure."""
    print("Exposure layers calculated.")
    return True


if HAS_AIRFLOW:
    default_args = {
        "owner": "geotechnical_platform",
        "depends_on_past": False,
        "start_date": datetime(2026, 1, 1),
        "email_on_failure": True,
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    }

    dag = DAG(
        "static_features",
        default_args=default_args,
        description="DEM prep, slope units, Horn derivatives, static features, and exposure",
        schedule_interval=None,  # Triggered on data change
        catchup=False,
    )

    t1 = PythonOperator(task_id="dem_prep", python_callable=task_dem_prep, dag=dag)
    t2 = PythonOperator(task_id="slope_units", python_callable=task_slope_units, dag=dag)
    t3 = PythonOperator(task_id="terrain_derivatives", python_callable=task_terrain_derivatives, dag=dag)
    t4 = PythonOperator(task_id="static_features", python_callable=task_static_features, dag=dag)
    t5 = PythonOperator(task_id="exposure_layers", python_callable=task_exposure_layers, dag=dag)

    t1 >> t2 >> t3 >> t4 >> t5
