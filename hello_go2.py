import time
import threading
import omni.usd
from pxr import Sdf
import omni.isaac.dynamic_control as dc
import omni.kit.commands
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from isaacsim.core.api import World

# Get the environment context
usd_context = omni.usd.get_context()
stage = usd_context.get_stage()
timeline = omni.timeline.get_timeline_interface()
stop_event = threading.Event()

# Define the prim path where the robot will be spawned and the asset path
robot_prim_path = "/World/UnitreeGo2"
robot_asset_path = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.5/Isaac/Robots/Unitree/Go2/go2.usd"

# Check if the robot is already spawned
if not stage.GetPrimAtPath(robot_prim_path):
    # Spawn the robot by creating a reference to its USD file
    print("Spawning Unitree GO2 robot at prim path:", robot_prim_path)
    omni.kit.commands.execute(
        "CreateReference",
        usd_context=usd_context,
        path_to=robot_prim_path,
        asset_path=robot_asset_path
    )
else:
    print("Robot is already spawned at prim path:", robot_prim_path)

# Acquire the Dynamic Control (DC) interface
# dc_interface = dc._dynamic_control.acquire_dynamic_control_interface()
# Retrieve the articulation ID of the spawned robot
# articulation = dc_interface.get_articulation(robot_prim_path)

print("test")
if articulation is None:
    print("Error: Unable to get the robot's articulation. Check the prim path and asset loading.")
else:
    print("Robot spawned successfully. Articulation ID:", articulation)
    
    # omni.timeline.get_timeline_interface().play() # We're going to assume the timeline is already playingt to start
    
    # Get the number of degrees of freedom (DOFs)
    num_dofs = dc_interface.get_articulation_dof_count(articulation)
    print(f"Robot has {num_dofs} joints.")

    class JointStatePublisher(Node):
        """ROS2 node that publishes joint states."""
        def __init__(self):
            super().__init__('joint_state_publisher')
            self.publisher_ = self.create_publisher(JointState, 'unitree_go2/joint_states', 10)
            self.timer_callback()
            self.start_time = time.time()
            self.duration = 15  # Run for 15 seconds

        def timer_callback(self):
            # Stop publishing after the set duration
            if time.time() - self.start_time > self.duration:
                self.get_logger().info("Finished publishing joint states.")
                stop_event.set()  # Signal the thread to stop
                return

            joint_state_msg = JointState()
            joint_state_msg.header.stamp = self.get_clock().now().to_msg()
            joint_state_msg.name = [f"joint_{i}" for i in range(num_dofs)]
            joint_state_msg.position = [
                dc_interface.get_articulation_dof_position(articulation, i) for i in range(num_dofs)
            ]
            self.publisher_.publish(joint_state_msg)
            self.get_logger().info(f"Published joint states: {joint_state_msg.position}")

    def run_ros2_node():
        """Runs the ROS2 joint state publisher in a background thread."""
        if not rclpy.utilities.ok():
            print("Initializing ROS2...")
            rclpy.init()
        node = JointStatePublisher()
        executor = rclpy.executors.MultiThreadedExecutor()
        executor.add_node(node)
        try:
            while rclpy.ok() and not stop_event.is_set():
                executor.spin_once(timeout_sec=0.1)
                time.sleep(0.01)
        except KeyboardInterrupt:
            pass
        finally:
            print("Shutting down ROS2...")
            node.destroy_node()
            rclpy.shutdown()
            print("ROS2 shut down successfully.")

    # Start the ROS2 publishing thread (daemonized so it doesn't block UI shutdown)
    ros_thread = threading.Thread(target=run_ros2_node, daemon=True)
    ros_thread.start()
    print("ROS2 node started.")

    # Instead of a blocking join, poll the thread in a loop:
    while ros_thread.is_alive():
        ros_thread.join(timeout=0.1)
        time.sleep(0.01)
    
    print("ROS2 node finished, simulation can now proceed with cleanup.")
    
    # Signal cleanup actions
    stop_event.set()
    # Optionally, pause the simulation timeline here:
    omni.timeline.get_timeline_interface().pause()
    
    # Remove the robot (if desired)
    # omni.kit.commands.execute("DeletePrims", paths=[robot_prim_path])
    # print("Robot removed from the scene.")