"""
Models for discrete/categorical tax variables.

Handles binary variables (is_itemizer, has_business) and categorical
variables (filing_status) separately from continuous variables.
"""

import torch
import torch.nn as nn


class BinaryVariableModel(nn.Module):
    """
    Model for binary tax variables (0/1).

    Examples: is_itemizer, has_business_income, has_capital_gains
    """

    def __init__(self, n_context: int, hidden_dim: int = 32):
        """
        Initialize binary variable model.

        Args:
            n_context: Number of context/conditioning features
            hidden_dim: Size of hidden layer
        """
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(n_context, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, context: torch.Tensor) -> torch.Tensor:
        """
        Predict probability of 1 given context.

        Args:
            context: Conditioning features [batch, n_context]

        Returns:
            Probability of 1 [batch, 1]
        """
        return self.network(context)


class CategoricalVariableModel(nn.Module):
    """
    Model for categorical tax variables (multiple classes).

    Example: filing_status (1=single, 2=married filing jointly, etc.)
    """

    def __init__(self, n_context: int, n_categories: int, hidden_dim: int = 32):
        """
        Initialize categorical variable model.

        Args:
            n_context: Number of context/conditioning features
            n_categories: Number of categories
            hidden_dim: Size of hidden layer
        """
        super().__init__()
        self.n_categories = n_categories

        self.network = nn.Sequential(
            nn.Linear(n_context, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, n_categories),
        )

    def forward(self, context: torch.Tensor) -> torch.Tensor:
        """
        Predict category probabilities given context.

        Args:
            context: Conditioning features [batch, n_context]

        Returns:
            Category probabilities [batch, n_categories]
        """
        logits = self.network(context)
        return torch.softmax(logits, dim=-1)


class DiscreteVariableSampler:
    """
    Sample discrete variables from predicted probabilities.

    Used during generation to convert model outputs to discrete values.
    """

    def sample_binary(
        self, probs: torch.Tensor, threshold: float = 0.5
    ) -> torch.Tensor:
        """
        Sample binary variables from probabilities.

        Args:
            probs: Probability of 1 [batch, 1]
            threshold: If None, sample stochastically. If float, threshold.

        Returns:
            Binary samples [batch, 1]
        """
        if threshold is not None:
            return (probs > threshold).long()
        else:
            return torch.bernoulli(probs).long()

    def sample_categorical(self, probs: torch.Tensor) -> torch.Tensor:
        """
        Sample categorical variables from probabilities.

        Args:
            probs: Category probabilities [batch, n_categories]

        Returns:
            Category indices [batch]
        """
        return torch.multinomial(probs, num_samples=1).squeeze(-1)


class DiscreteModelCollection(nn.Module):
    """
    Collection of discrete variable models.

    Manages multiple binary and categorical models for different variables.
    """

    def __init__(
        self,
        n_context: int,
        binary_vars: list,
        categorical_vars: dict,
        hidden_dim: int = 32,
    ):
        """
        Initialize collection of discrete models.

        Args:
            n_context: Number of context features
            binary_vars: List of binary variable names
            categorical_vars: Dict of {var_name: n_categories}
            hidden_dim: Size of hidden layers
        """
        super().__init__()
        self.binary_vars = binary_vars
        self.categorical_vars = categorical_vars

        # Binary models
        self.binary_models = nn.ModuleDict(
            {var: BinaryVariableModel(n_context, hidden_dim) for var in binary_vars}
        )

        # Categorical models
        self.categorical_models = nn.ModuleDict(
            {
                var: CategoricalVariableModel(n_context, n_cats, hidden_dim)
                for var, n_cats in categorical_vars.items()
            }
        )

        self.sampler = DiscreteVariableSampler()

    def forward(self, context: torch.Tensor) -> dict:
        """
        Predict probabilities for all discrete variables.

        Args:
            context: Conditioning features

        Returns:
            Dict of {var_name: probabilities}
        """
        result = {}

        for var in self.binary_vars:
            result[var] = self.binary_models[var](context)

        for var in self.categorical_vars:
            result[var] = self.categorical_models[var](context)

        return result

    def sample(self, context: torch.Tensor) -> dict:
        """
        Sample all discrete variables.

        Args:
            context: Conditioning features

        Returns:
            Dict of {var_name: samples}
        """
        probs = self.forward(context)
        result = {}

        for var in self.binary_vars:
            result[var] = self.sampler.sample_binary(probs[var])

        for var in self.categorical_vars:
            result[var] = self.sampler.sample_categorical(probs[var])

        return result

    def log_prob(self, context: torch.Tensor, targets: dict) -> torch.Tensor:
        """
        Compute log probability of discrete variables.

        Args:
            context: Conditioning features
            targets: Dict of {var_name: values}

        Returns:
            Total log probability [batch]
        """
        probs = self.forward(context)
        total_log_prob = 0.0

        for var in self.binary_vars:
            p = probs[var]
            y = targets[var].float()
            # Binary cross entropy
            log_p = y * torch.log(p + 1e-8) + (1 - y) * torch.log(1 - p + 1e-8)
            total_log_prob = total_log_prob + log_p.sum(dim=-1)

        for var in self.categorical_vars:
            p = probs[var]
            y = targets[var].long()
            # Categorical cross entropy
            log_p = torch.log(p.gather(1, y.unsqueeze(-1)) + 1e-8)
            total_log_prob = total_log_prob + log_p.squeeze(-1)

        return total_log_prob
