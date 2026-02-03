
import os
import sys
import unittest
from app import app
from utils import calculate_grade

class SmokeTest(unittest.TestCase):
    def test_calculate_grade(self):
        self.assertEqual(calculate_grade(95), 'A+')
        self.assertEqual(calculate_grade(85), 'A')
        self.assertEqual(calculate_grade(75), 'B')
        self.assertEqual(calculate_grade(65), 'C')
        self.assertEqual(calculate_grade(55), 'D')
        self.assertEqual(calculate_grade(45), 'F')
        self.assertEqual(calculate_grade('invalid'), 'F')
        

if __name__ == '__main__':
    unittest.main()
