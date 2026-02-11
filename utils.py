def calculate_grade(marks):
    """
    Calculate grade based on marks.
    Scale: A (70-100), B (60-69), C (50-59), D (45-49), E (40-44), F (0-39)
    """
    try:
        marks = float(marks)
    except (ValueError, TypeError):
        return 'F'
        
    if marks >= 70:
        return 'A'
    elif marks >= 60:
        return 'B'
    elif marks >= 50:
        return 'C'
    elif marks >= 45:
        return 'D'
    elif marks >= 40:
        return 'E'
    else:
        return 'F'

def get_grade_points(grade):
    """
    Assign points based on grade (5.0 scale).
    """
    points = {
        'A': 5,
        'B': 4,
        'C': 3,
        'D': 2,
        'E': 1,
        'F': 0
    }
    return points.get(grade, 0)
