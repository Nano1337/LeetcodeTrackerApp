
def generate_md(next_problem, approach, challenges, solution_code):
    return f"""# {next_problem.name}

    ## Approach
    {approach}

    ## Challenges
    {challenges}

    ## Solution```python 
    {solution_code}
    ```
        """