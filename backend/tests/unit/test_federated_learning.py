"""
联邦学习系统测试
"""
import pytest
import asyncio
import numpy as np
from datetime import datetime
from typing import List, Dict, Any

from app.services.federated_learning import (
    PrivacyMechanism,
    PrivacyConfig,
    ModelUpdate,
    GlobalModel,
    FederatedClient,
    DifferentialPrivacy,
    FederatedCoordinator
)


# ============== Fixtures ==============

@pytest.fixture
def privacy_config():
    """隐私配置fixture"""
    return PrivacyConfig(
        epsilon=1.0,
        delta=1e-5,
        mechanism=PrivacyMechanism.DIFFERENTIAL_PRIVACY
    )


@pytest.fixture
def federated_client(privacy_config):
    """联邦客户端fixture"""
    return FederatedClient("test_client", privacy_config)


@pytest.fixture
def federated_coordinator(privacy_config):
    """联邦协调器fixture"""
    return FederatedCoordinator(privacy_config)


@pytest.fixture
def sample_global_model():
    """示例全局模型"""
    return GlobalModel(
        model_id="test_model",
        weights={
            "layer1": np.random.randn(10, 5).tolist(),
            "layer2": np.random.randn(5, 2).tolist()
        },
        version=1,
        round_count=0
    )


# ============== 单元测试：隐私配置 ==============

class TestPrivacyConfig:
    """隐私配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = PrivacyConfig()
        
        assert config.epsilon == 1.0
        assert config.delta == 1e-5
        assert config.mechanism == PrivacyMechanism.DIFFERENTIAL_PRIVACY
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = PrivacyConfig(
            epsilon=0.5,
            delta=1e-10,
            mechanism=PrivacyMechanism.HOMOMORPHIC_ENCRYPTION
        )
        
        assert config.epsilon == 0.5
        assert config.delta == 1e-10
        assert config.mechanism == PrivacyMechanism.HOMOMORPHIC_ENCRYPTION


# ============== 单元测试：模型更新 ==============

class TestModelUpdate:
    """模型更新测试"""
    
    def test_model_update_creation(self):
        """测试模型更新创建"""
        update = ModelUpdate(
            client_id="client_1",
            round_id=1,
            weights={"layer1": [1.0, 2.0, 3.0]},
            sample_count=100
        )
        
        assert update.client_id == "client_1"
        assert update.round_id == 1
        assert len(update.weights["layer1"]) == 3
        assert update.sample_count == 100
    
    def test_checksum_computation(self):
        """测试校验和计算"""
        update = ModelUpdate(
            client_id="client_1",
            round_id=1,
            weights={"layer1": [1.0, 2.0, 3.0]}
        )
        
        checksum1 = update.compute_checksum()
        checksum2 = update.compute_checksum()
        
        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA256 hex length
    
    def test_apply_noise(self):
        """测试噪声应用"""
        update = ModelUpdate(
            client_id="client_1",
            round_id=1,
            weights={"layer1": [1.0, 2.0, 3.0, 4.0, 5.0]}
        )
        
        original_weights = update.weights["layer1"].copy()
        update.apply_noise(noise_scale=0.1)
        
        # 权重应该被修改
        assert update.weights["layer1"] != original_weights


# ============== 单元测试：差分隐私 ==============

class TestDifferentialPrivacyMechanisms:
    """差分隐私机制测试"""
    
    def test_laplace_mechanism(self):
        """测试拉普拉斯机制"""
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-5)
        
        data = np.array([1.0, 2.0, 3.0])
        noisy_data = dp.add_laplace_noise(data, sensitivity=1.0)
        
        assert noisy_data.shape == data.shape
        assert not np.allclose(noisy_data, data)
    
    def test_gaussian_mechanism(self):
        """测试高斯机制"""
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-5)
        
        data = np.array([1.0, 2.0, 3.0])
        noisy_data = dp.add_gaussian_noise(data, sensitivity=1.0)
        
        assert noisy_data.shape == data.shape
        assert not np.allclose(noisy_data, data)
    
    def test_privatize_loss(self):
        """测试损失私有化"""
        dp = DifferentialPrivacy(epsilon=1.0)
        
        original_loss = 0.5
        private_loss = dp.privatize_loss(original_loss)
        
        # 应该添加了噪声
        assert private_loss != original_loss
    
    def test_gradient_clipping(self):
        """测试梯度裁剪"""
        dp = DifferentialPrivacy(epsilon=1.0)
        
        gradient = np.array([10.0, 5.0, 3.0])  # norm > 1
        clipped_gradient = dp.privatize_gradient(gradient, sensitivity=1.0)
        
        # 裁剪后的梯度范数应该 <= sensitivity
        assert np.linalg.norm(clipped_gradient) <= 1.0 * 1.1  # 允许一些误差


# ============== 集成测试：联邦客户端 ==============

@pytest.mark.asyncio
class TestFederatedClient:
    """联邦客户端测试"""
    
    async def test_client_initialization(self, federated_client):
        """测试客户端初始化"""
        assert federated_client.client_id == "test_client"
        assert federated_client.participation_rounds == 0
        assert federated_client.training_samples == 0
    
    async def test_local_training(self, federated_client, sample_global_model):
        """测试本地训练"""
        update = await federated_client.train_local(sample_global_model)
        
        assert update.client_id == "test_client"
        assert update.round_id == 1
        assert update.sample_count > 0
        assert update.checksum is not None
    
    async def test_client_evaluation(self, federated_client):
        """测试客户端评估"""
        metrics = await federated_client.evaluate()
        
        assert "accuracy" in metrics
        assert "loss" in metrics
        assert 0 <= metrics["accuracy"] <= 1
        assert metrics["loss"] >= 0


# ============== 集成测试：联邦协调器 ==============

@pytest.mark.asyncio
class TestFederatedCoordinator:
    """联邦协调器测试"""
    
    def test_coordinator_initialization(self, federated_coordinator):
        """测试协调器初始化"""
        assert federated_coordinator.current_round == 0
        assert len(federated_coordinator.clients) == 0
        assert federated_coordinator.global_model is None
    
    def test_model_initialization(self, federated_coordinator):
        """测试模型初始化"""
        weight_shapes = {
            "layer1": (10, 5),
            "layer2": (5, 2)
        }
        
        model = federated_coordinator.initialize_model(weight_shapes)
        
        assert model is not None
        assert federated_coordinator.global_model is not None
        assert len(model.weights) == 2
    
    def test_client_registration(self, federated_coordinator):
        """测试客户端注册"""
        client = FederatedClient("new_client", PrivacyConfig())
        client_id = federated_coordinator.register_client(client)
        
        assert client_id == "new_client"
        assert len(federated_coordinator.clients) == 1
    
    async def test_training_round(self, federated_coordinator):
        """测试训练轮次"""
        # 初始化模型
        federated_coordinator.initialize_model({"layer1": (10, 5), "layer2": (5, 2)})
        
        # 注册客户端
        for i in range(3):
            client = FederatedClient(f"client_{i}", PrivacyConfig())
            federated_coordinator.register_client(client)
        
        # 运行训练轮次
        result = await federated_coordinator.run_training_round()
        
        assert result["round_id"] == 1
        assert federated_coordinator.current_round == 1
        assert federated_coordinator.global_model.version == 1
    
    async def test_federated_averaging(self, federated_coordinator):
        """测试联邦平均"""
        # 创建多个更新
        updates = []
        for i in range(3):
            update = ModelUpdate(
                client_id=f"client_{i}",
                round_id=1,
                weights={
                    "layer1": np.ones((10, 5)).tolist(),
                    "layer2": np.ones((5, 2)).tolist()
                },
                sample_count=100 * (i + 1)
            )
            updates.append(update)
        
        # 聚合
        aggregated = await federated_coordinator.federated_averaging(updates)
        
        assert "layer1" in aggregated
        assert "layer2" in aggregated
        assert len(aggregated["layer1"]) == 10
    
    async def test_full_training(self, federated_coordinator):
        """测试完整训练"""
        # 初始化
        federated_coordinator.initialize_model({"layer1": (10, 5), "layer2": (5, 2)})
        
        # 注册客户端
        for i in range(2):
            client = FederatedClient(f"client_{i}", PrivacyConfig())
            federated_coordinator.register_client(client)
        
        # 完整训练
        result = await federated_coordinator.full_training(num_rounds=3)
        
        assert result["num_rounds"] == 3
        assert len(result["history"]) == 3
        assert federated_coordinator.current_round == 3


# ============== 性能测试 ==============

@pytest.mark.asyncio
class TestPerformance:
    """性能测试"""
    
    @pytest.mark.timeout(30)
    async def test_training_speed(self, federated_coordinator):
        """测试训练速度"""
        import time
        
        federated_coordinator.initialize_model({"layer1": (10, 5), "layer2": (5, 2)})
        
        for i in range(3):
            client = FederatedClient(f"client_{i}", PrivacyConfig())
            federated_coordinator.register_client(client)
        
        start = time.time()
        await federated_coordinator.run_training_round()
        elapsed = time.time() - start
        
        assert elapsed < 10, f"Training took too long: {elapsed}s"
    
    @pytest.mark.timeout(60)
    async def test_scalability(self, federated_coordinator):
        """测试可扩展性"""
        import time
        
        federated_coordinator.initialize_model({"layer1": (100, 50), "layer2": (50, 10)})
        
        # 注册多个客户端
        for i in range(10):
            client = FederatedClient(f"client_{i}", PrivacyConfig())
            federated_coordinator.register_client(client)
        
        start = time.time()
        await federated_coordinator.run_training_round()
        elapsed = time.time() - start
        
        assert elapsed < 30, f"Scalability test took too long: {elapsed}s"


# ============== 安全测试 ==============

class TestSecurity:
    """安全测试"""
    
    def test_checksum_integrity(self):
        """测试校验和完整性"""
        update = ModelUpdate(
            client_id="client_1",
            round_id=1,
            weights={"layer1": [1.0, 2.0, 3.0]}
        )
        
        # 修改权重后校验和应该变化
        original_checksum = update.compute_checksum()
        update.weights["layer1"] = [4.0, 5.0, 6.0]
        new_checksum = update.compute_checksum()
        
        assert original_checksum != new_checksum
    
    def test_privacy_guarantee(self):
        """测试隐私保证"""
        dp = DifferentialPrivacy(epsilon=0.1, delta=1e-5)  # 严格的隐私
        
        # 多次扰动同一数据
        data = np.array([1.0, 2.0, 3.0])
        noisy_data_list = [dp.add_gaussian_noise(data, sensitivity=1.0) for _ in range(10)]
        
        # 应该产生不同的结果
        for i in range(len(noisy_data_list) - 1):
            assert not np.allclose(noisy_data_list[i], noisy_data_list[i + 1], atol=1e-3)


# ============== 边界测试 ==============

class TestEdgeCases:
    """边界情况测试"""
    
    async def test_empty_weights(self, federated_coordinator):
        """测试空权重"""
        federated_coordinator.initialize_model({})
        assert federated_coordinator.global_model is not None
    
    async def test_single_client(self, federated_coordinator):
        """测试单客户端"""
        federated_coordinator.initialize_model({"layer1": (10, 5)})
        client = FederatedClient("single_client", PrivacyConfig())
        federated_coordinator.register_client(client)
        
        result = await federated_coordinator.run_training_round()
        assert result["num_clients"] >= 1
    
    async def test_zero_samples(self, federated_client, sample_global_model):
        """测试零样本"""
        federated_client.training_samples = 0
        update = await federated_client.train_local(sample_global_model)
        assert update.sample_count > 0  # 应该有默认样本数


# ============== 运行测试 ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.federated_learning"])
