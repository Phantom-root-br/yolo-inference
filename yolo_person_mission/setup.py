from setuptools import find_packages, setup


package_name = 'yolo_person_mission'


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name],
        ),
        (
            'share/' + package_name,
            ['package.xml'],
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='HARPia Team',
    maintainer_email='harpia@example.com',
    description=(
        'PX4 square-spiral search, visual centering, '
        '30-second tracking and return-home mission.'
    ),
    license='MIT',
    entry_points={
        'console_scripts': [
            'person_mission = '
            'yolo_person_mission.person_mission_node:main',
        ],
    },
)
