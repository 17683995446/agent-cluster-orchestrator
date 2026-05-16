"""
元学习系统测试
"""
import pytest
import asyncio
import numpy as np
from datetime import datetime
from typing import List, Dict, Any

from app.services.meta_learning import (
    MetaLearningAlgorithm,
    Task,
    MetaParameters,
    BaseMetaModel,
    MAML,
    Reptile,
    PrototypicalNetwork,
    MetaLearningTrainer,
    generate_synthetic_task
)


# ============== Fixtures ==============

@pytest.fixture
def base_model():
    """基础模型fixture"""
    return BaseMetaModel(input_dim=10, output_dim=5)


@pytest.fixture
def maml_trainer(base_model):
    """MAML训练器fixture"""
    return MAML(base_model, inner_lr=0.01, outer_lr=0.001)


@pytest.fixture
def reptile_trainer(base_model):
    """Reptile训练器fixture"""
    return Reptile(base_model, step_size=0.01)


@pytest.fixture
def prototypical_network():
    """原型网络fixture"""
    return PrototypicalNetwork(embedding_dim=64)


@pytest.fixture
def synthetic_tasks():
    """合成任务fixture"""
    return [generate_synthetic_task(num_shot=5, num_way=3, input_dim=10) for _ in range(10)]


# ============== 单元测试：基础模型 ==============

class TestBaseMetaModel:
    """基础元学习模型测试"""
    
    def test_model_initialization(self):
        """测试模型初始化"""
        model = BaseMetaModel(input_dim=10, output_dim=5)
        
        assert model.input_dim == 10
        assert model.output_dim == 5
        assert "layer1" in model.weights
        assert "layer2" in model.weights
    
    def test_forward_pass(self):
        """测试前向传播"""
        model = BaseMetaModel(input_dim=10, output_dim=5)
        
        x = np.random.randn(5, 10)
        output = model.forward(x)
        
        assert output.shape == (5, 5)
    
    def test_compute_loss(self):
        """测试损失计算"""
        model = BaseMetaModel(input_dim=10, output_dim=5)
        
        x = np.random.randn(5, 10)
        y = np.eye(5)  # one-hot编码
        
        loss, gradients = model.compute_loss(x, y)
        
        assert isinstance(loss, float)
        assert loss >= 0
        assert "layer1" in gradients
    
    def test_get_set_parameters(self):
        """测试参数获取和设置"""
        model = BaseMetaModel(input_dim=10, output_dim=5)
        
        params = model.get_parameters()
        assert "layer1" in params.weights
        
        model.set_parameters(params)
        new_params = model.get_parameters()
        
        # 参数应该相同
        assert np.allclose(
            np.array(params.weights["layer1"]),
            np.array(new_params.weights["layer1"])
        )


# ============== 单元测试：MAML ==============

class TestMAML:
    """MAML算法测试"""
    
    def test_maml_initialization(self, base_model):
        """测试MAML初始化"""
        maml = MAML(base_model)
        
        assert maml.inner_lr == 0.01
        assert maml.outer_lr == 0.001
        assert maml.num_inner_steps == 1
    
    def test_inner_loop(self, maml_trainer, synthetic_tasks):
        """测试内循环"""
        model = maml_trainer.model
        task = synthetic_tasks[0]
        
        adapted_model = maml_trainer.inner_loop(model, task)
        
        assert adapted_model is not None
        assert adapted_model is not model
    
    def test_fast_adapt(self, maml_trainer, synthetic_tasks):
        """测试快速适应"""
        task = synthetic_tasks[0]
        
        adapted_model = maml_trainer.fast_adapt(task)
        
        assert adapted_model is not None


@pytest.mark.asyncio
class TestMAMLTraining:
    """MAML训练测试"""
    
    @pytest.mark.timeout(30)
    async def test_meta_training(self, maml_trainer, synthetic_tasks):
        """测试元训练"""
        # 只训练几个epoch以加快测试
        result = maml_trainer.meta_train(synthetic_tasks[:5], num_epochs=3)
        
        assert result["algorithm"] == "MAML"
        assert result["num_epochs"] == 3
        assert "history" in result
        assert len(result["history"]) == 3


# ============== 单元测试：Reptile ==============

class TestReptile:
    """Reptile算法测试"""
    
    def test_reptile_initialization(self, base_model):
        """测试Reptile初始化"""
        reptile = Reptile(base_model)
        
        assert reptile.step_size == 0.001
        assert reptile.num_inner_steps == 3


@pytest.mark.asyncio
class TestReptileTraining:
    """Reptile训练测试"""
    
    @pytest.mark.timeout(30)
    async def test_meta_training(self, reptile_trainer, synthetic_tasks):
        """测试Reptile元训练"""
        result = reptile_trainer.meta_train(synthetic_tasks[:5], num_epochs=3)
        
        assert result["algorithm"] == "Reptile"
        assert result["num_epochs"] == 3
        assert "history" in result


# ============== 单元测试：原型网络 ==============

class TestPrototypicalNetwork:
    """原型网络测试"""
    
    def test_prototypical_initialization(self):
        """测试原型网络初始化"""
        proto = PrototypicalNetwork(embedding_dim=64)
        
        assert proto.embedding_dim == 64
        assert len(proto.prototypes) == 0
    
    def test_compute_prototypes(self, prototypical_network):
        """测试原型计算"""
        support_set = {
            "class_1": [[1.0, 2.0, 3.0], [1.1, 2.1, 3.1]],
            "class_2": [[4.0, 5.0, 6.0], [4.1, 5.1, 6.1]]
        }
        
        # 需要调整embedding_dim
        proto = PrototypicalNetwork(embedding_dim=3)
        prototypes = proto.compute_prototypes(support_set)
        
        assert "class_1" in prototypes
        assert "class_2" in prototypes
        assert len(prototypes["class_1"]) == 3
    
    def test_classify(self, prototypical_network):
        """测试分类"""
        proto = PrototypicalNetwork(embedding_dim=3)
        proto.prototypes = {
            "class_1": [1.0, 2.0, 3.0],
            "class_2": [4.0, 5.0, 6.0]
        }
        
        query = [1.0, 2.0, 3.0]
        predicted_class, distance = proto.classify(query)
        
        assert predicted_class == "class_1"
        assert distance >= 0


# ============== 单元测试：元学习训练器 ==============

class TestMetaLearningTrainer:
    """元学习训练器测试"""
    
    def test_trainer_initialization(self):
        """测试训练器初始化"""
        trainer = MetaLearningTrainer(MetaLearningAlgorithm.MAML)
        
        assert trainer.algorithm == MetaLearningAlgorithm.MAML
        assert trainer.model is None
        assert trainer.trainer is None
    
    def test_initialize(self):
        """测试训练器初始化"""
        trainer = MetaLearningTrainer(MetaLearningAlgorithm.MAML)
        trainer.initialize(input_dim=10, output_dim=5)
        
        assert trainer.model is not None
        assert trainer.trainer is not None


@pytest.mark.asyncio
class TestMetaLearningTrainerTraining:
    """元学习训练器训练测试"""
    
    @pytest.mark.timeout(30)
    async def test_train_maml(self, synthetic_tasks):
        """测试MAML训练"""
        trainer = MetaLearningTrainer(MetaLearningAlgorithm.MAML)
        trainer.initialize(input_dim=10, output_dim=5)
        
        result = await trainer.train(synthetic_tasks[:3], num_epochs=2)
        
        assert "algorithm" in result
        assert "history" in result


# ============== 工具函数测试 ==============

class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_generate_synthetic_task(self):
        """测试合成任务生成"""
        task = generate_synthetic_task(num_shot=5, num_way=3, input_dim=10)
        
        assert task.task_type == "classification"
        assert task.num_shot == 5
        assert task.num_way == 3
        
        # 检查数据结构
        assert "inputs" in task.support_data
        assert "targets" in task.support_data
        assert len(task.support_data["inputs"]) == 5 * 3
        assert len(task.support_data["targets"]) == 5 * 3
    
    def test_task_differentiation(self):
        """测试任务差异性"""
        tasks = [generate_synthetic_task() for _ in range(10)]
        
        task_ids = [t.task_id for t in tasks]
        assert len(task_ids) == len(set(task_ids))  # 所有ID应该唯一


# ============== 性能测试 ==============

@pytest.mark.asyncio
class TestPerformance:
    """性能测试"""
    
    @pytest.mark.timeout(60)
    async def test_maml_speed(self, synthetic_tasks):
        """测试MAML速度"""
        import time
        
        trainer = MetaLearningTrainer(MetaLearningAlgorithm.MAML)
        trainer.initialize(input_dim=20, output_dim=10)
        
        start = time.time()
        await trainer.train(synthetic_tasks, num_epochs=5)
        elapsed = time.time() - start
        
        assert elapsed < 30, f"MAML took too long: {elapsed}s"
    
    @pytest.mark.timeout(60)
    async def test_reptile_speed(self, synthetic_tasks):
        """测试Reptile速度"""
        import time
        
        trainer = MetaLearningTrainer(MetaLearningAlgorithm.REPTILE)
        trainer.initialize(input_dim=20, output_dim=10)
        
        start = time.time()
        await trainer.train(synthetic_tasks, num_epochs=5)
        elapsed = time.time() - start
        
        assert elapsed < 30, f"Reptile took too long: {elapsed}s"


# ============== 边界测试 ==============

class TestEdgeCases:
    """边界情况测试"""
    
    def test_single_sample_task(self):
        """测试单样本任务"""
        task = generate_synthetic_task(num_shot=1, num_way=2, input_dim=10)
        
        assert task.num_shot == 1
        assert len(task.support_data["inputs"]) == 2
    
    def test_large_dimension(self):
        """测试大维度"""
        model = BaseMetaModel(input_dim=1000, output_dim=500)
        
        x = np.random.randn(10, 1000)
        output = model.forward(x)
        
        assert output.shape == (10, 500)
    
    def test_small_learning_rate(self):
        """测试小学习率"""
        model = BaseMetaModel(input_dim=10, output_dim=5)
        maml = MAML(model, inner_lr=1e-6, outer_lr=1e-7)
        
        assert maml.inner_lr == 1e-6
        assert maml.outer_lr == 1e-7


# ============== 对比测试 ==============

@pytest.mark.asyncio
class TestAlgorithmComparison:
    """算法对比测试"""
    
    @pytest.mark.timeout(60)
    async def test_maml_vs_reptile(self, synthetic_tasks):
        """测试MAML vs Reptile"""
        # MAML
        maml_trainer = MetaLearningTrainer(MetaLearningAlgorithm.MAML)
        maml_trainer.initialize(input_dim=10, output_dim=5)
        maml_result = await maml_trainer.train(synthetic_tasks, num_epochs=3)
        
        # Reptile
        reptile_trainer = MetaLearningTrainer(MetaLearningAlgorithm.REPTILE)
        reptile_trainer.initialize(input_dim=10, output_dim=5)
        reptile_result = await reptile_trainer.train(synthetic_tasks, num_epochs=3)
        
        # 两者都应该有历史记录
        assert "history" in maml_result
        assert "history" in reptile_result


# ============== 运行测试 ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.meta_learning"])
